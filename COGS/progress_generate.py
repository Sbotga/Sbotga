from PIL import Image, ImageDraw, ImageFont
from dataclasses import dataclass
from math import ceil
from io import BytesIO


@dataclass
class DifficultyCategory:
    difficulty: int
    ap_count: int
    fc_count: int
    clear_count: int
    all_count: int


@dataclass
class StrDifficultyCategory:
    difficulty: str
    ap_count: int
    fc_count: int
    clear_count: int
    all_count: int


def generate_general_progress(data: list):
    # fonts
    FONTPATH = "DATA/data/ASSETS/rodinntlg_eb.otf"
    FONTPATH_LIGHT = "DATA/data/ASSETS/rodinntlg_m.otf"

    # image params
    IMAGE_WIDTH = 2000
    HEADER_HEIGHT = 200
    SUB_HEADER_HEIGHT = 50

    CARD_GUTTER_HEIGHT = 50
    CARD_GUTTER_WIDTH = 50
    CARD_WIDTH = IMAGE_WIDTH - (CARD_GUTTER_WIDTH * 2)

    # Badge (difficulty title) parameters
    BADGE_HPAD = 40  # horizontal padding inside badge
    BADGE_VPAD = 20  # vertical padding inside badge
    badge_font = ImageFont.truetype(FONTPATH, 70)

    # Donut chart parameters
    DONUT_SIZE = 350
    DONUT_PADDING = 30
    DONUT_THICKNESS = 75

    # Counts panel styling
    COUNT_PADDING_Y = 30  # vertical padding for counts panel
    COUNT_PADDING_X = 30
    COUNT_FONT_SIZE = 50
    COUNT_FONT_CATEGORIES = ImageFont.truetype(FONTPATH, COUNT_FONT_SIZE)
    COUNT_FONT_TEXT = ImageFont.truetype(FONTPATH_LIGHT, COUNT_FONT_SIZE)
    COUNT_FONT_COLOR = "white"
    line_spacing = 20  # spacing between lines

    FC_COLOR = "#e83ce3"
    CLEAR_COLOR = "#F9D442"
    NOT_CLEAR_COLOR = "#38383a"

    ALL_AP_ICON = "DATA/data/ASSETS/normal_ap.png"
    ALL_FC_ICON = "DATA/data/ASSETS/normal_fc.png"
    ICON_PADDING = 20

    BACKGROUND_IMG = "DATA/data/ASSETS/hug.png"

    # Difficulty color images used for sampling badge/donut backgrounds.
    difficulty_colors = {
        "append": "DATA/data/ASSETS/append_color.jpg",
        "hard": "DATA/data/ASSETS/hard_color.jpg",
        "normal": "DATA/data/ASSETS/normal_color.jpg",
        "easy": "DATA/data/ASSETS/easy_color.jpg",
        "master": "DATA/data/ASSETS/master_color.jpg",
        "expert": "DATA/data/ASSETS/expert_color.jpg",
    }

    difficulty_images = {
        key: Image.open(path)
        .resize((CARD_WIDTH, DONUT_SIZE), Image.LANCZOS)
        .convert("RGBA")
        for key, path in difficulty_colors.items()
    }

    # Helper: draw a vertical gradient on an image.
    def draw_gradient(img, start, end):
        px = img.load()
        for y in range(img.height):
            color = tuple(
                int(start[i] + (end[i] - start[i]) * y / img.height) for i in range(3)
            )
            for x in range(img.width):
                px[x, y] = color

    def main(data: list[StrDifficultyCategory]):
        # --- Compute maximum badge dimensions (all badges will use the largest size (we add 2 characters for padding)) ---
        max_text_width = 0
        max_text_height = 0
        for diff in data:
            text = diff.difficulty.upper() + "hi"
            w = badge_font.getlength(text)
            bbox = badge_font.getbbox(text)
            h = bbox[3] - bbox[1]
            if w > max_text_width:
                max_text_width = w
            if h > max_text_height:
                max_text_height = h
        max_badge_width = int(max_text_width + 2 * BADGE_HPAD)
        max_badge_height = int(max_text_height + 2 * BADGE_VPAD)

        # --- Determine counts panel height dynamically ---
        sample_text = "ALL PERFECT"
        bbox = COUNT_FONT_CATEGORIES.getbbox(sample_text)
        text_height = bbox[3] - bbox[1]
        counts_panel_height = (
            COUNT_PADDING_Y + (text_height * 4) + (line_spacing * 3) + COUNT_PADDING_Y
        )

        # The content row (donut and counts) height is the larger of DONUT_SIZE and counts_panel_height.
        row_height = max(DONUT_SIZE, counts_panel_height)

        # We'll add extra padding around the white card background.
        white_card_padding = 30
        # The white card background area will fill the entire card container.
        # We set CARD_CONTENT_HEIGHT to row_height plus vertical padding.
        CARD_CONTENT_HEIGHT = row_height + (white_card_padding * 2)

        # The overall card container height must allow the badge (which will overlap above)
        CARD_CONTAINER_HEIGHT = CARD_CONTENT_HEIGHT + (max_badge_height // 2)

        # Total number of cards and overall image height.
        number_of_cards = len(data)
        total_height = (
            HEADER_HEIGHT
            + SUB_HEADER_HEIGHT
            + (number_of_cards * CARD_CONTAINER_HEIGHT)
            + ((number_of_cards + 1) * CARD_GUTTER_HEIGHT)
        )

        new_im = Image.new("RGBA", (IMAGE_WIDTH, total_height))

        # Draw overall background image.
        background_img = Image.open(BACKGROUND_IMG)
        original_width, original_height = background_img.size
        if original_height > total_height:
            background_img = background_img.crop((0, 0, original_width, total_height))
        else:
            background_img = background_img.resize((original_width, total_height))
        background_img = background_img.resize((IMAGE_WIDTH, total_height))
        new_im.paste(background_img, (0, 0))

        im_draw = ImageDraw.Draw(new_im)

        # Draw header.
        im_draw.rectangle(
            [(0, 0), (new_im.width, HEADER_HEIGHT)], fill="#b4ccfa", outline="#00194a"
        )
        header_font = ImageFont.truetype(FONTPATH, 96)
        im_draw.text(
            (20, 28), "Your PJSK All Difficulty Summary", fill="black", font=header_font
        )
        watermark = ImageFont.truetype(FONTPATH, 60)
        im_draw.text((20, 130), "Generated by Sbotga", fill="black", font=watermark)

        # Process each card.
        for i, diff in enumerate(data):
            y_card = (
                HEADER_HEIGHT
                + SUB_HEADER_HEIGHT
                + CARD_GUTTER_HEIGHT
                + i * (CARD_CONTAINER_HEIGHT + CARD_GUTTER_HEIGHT)
            )

            # Create card container.
            card_container = Image.new(
                "RGBA", (CARD_WIDTH, CARD_CONTAINER_HEIGHT), (255, 255, 255, 0)
            )
            container_draw = ImageDraw.Draw(card_container)
            CARD_RADIUS = 25

            # --- Draw white card background (expanded to include padding) ---
            white_rect = (
                white_card_padding,
                white_card_padding,
                CARD_WIDTH - white_card_padding,
                CARD_CONTAINER_HEIGHT - white_card_padding,
            )
            container_draw.rounded_rectangle(
                white_rect, radius=CARD_RADIUS, fill="white"
            )

            # --- Inside white card, draw the donut and counts panel.
            # Define the content area inside the white card.
            content_area_x = white_card_padding
            content_area_y = white_card_padding
            content_area_width = CARD_WIDTH - 2 * white_card_padding
            content_area_height = CARD_CONTAINER_HEIGHT - 2 * white_card_padding

            # Position the donut: leave DONUT_PADDING from the left.
            donut_x = content_area_x + DONUT_PADDING
            donut_y = content_area_y + (content_area_height - DONUT_SIZE) // 2

            # Create the donut chart.
            donut_img = Image.new("RGBA", (DONUT_SIZE, DONUT_SIZE), (255, 255, 255, 0))
            donut_draw = ImageDraw.Draw(donut_img)

            # Compute pie slice angles.
            aped = diff.ap_count
            fced = diff.fc_count - diff.ap_count
            cleared = diff.clear_count - diff.fc_count
            not_cleared = diff.all_count - diff.clear_count

            percentage_ap = aped / diff.all_count
            percentage_fc = fced / diff.all_count
            percentage_clear = cleared / diff.all_count
            percentage_not_clear = not_cleared / diff.all_count

            angle_ap = percentage_ap * 360
            angle_fc = angle_ap + (percentage_fc * 360)
            angle_clear = angle_fc + (percentage_clear * 360)
            angle_not_clear = angle_clear + (percentage_not_clear * 360)

            pie_location = (0, 0, DONUT_SIZE, DONUT_SIZE)
            donut_draw.pieslice(pie_location, 0, 360, fill="white")

            # For ALL PERFECT portion, use a gradient from the ALL_AP_ICON sample.
            ap_color_sample = Image.open(ALL_AP_ICON)
            color_top = ap_color_sample.getpixel((ap_color_sample.size[0] // 2, 60))
            color_bottom = ap_color_sample.getpixel(
                (ap_color_sample.size[0] // 2, ap_color_sample.size[1] - 60)
            )
            gradient = Image.new("RGB", (DONUT_SIZE, DONUT_SIZE))
            draw_gradient(gradient, color_top, color_bottom)
            im_mask = Image.new("L", (DONUT_SIZE, DONUT_SIZE), 0)
            d_mask = ImageDraw.Draw(im_mask)
            d_mask.pieslice((0, 0, DONUT_SIZE, DONUT_SIZE), 0, angle_ap, fill=255)
            donut_img.paste(gradient, (0, 0), im_mask)

            donut_draw.pieslice(pie_location, angle_ap, angle_fc, fill=FC_COLOR)
            donut_draw.pieslice(pie_location, angle_fc, angle_clear, fill=CLEAR_COLOR)
            donut_draw.pieslice(
                pie_location, angle_clear, angle_not_clear, fill=NOT_CLEAR_COLOR
            )

            donut_draw.ellipse(
                (
                    DONUT_THICKNESS,
                    DONUT_THICKNESS,
                    DONUT_SIZE - DONUT_THICKNESS,
                    DONUT_SIZE - DONUT_THICKNESS,
                ),
                fill="white",
            )

            # Overlay icon if fully ALL PERFECT or FULL COMBO.
            icon_size = DONUT_SIZE - (DONUT_THICKNESS * 2) - (ICON_PADDING * 2)
            icon_x = (DONUT_SIZE - icon_size) // 2
            icon_y = (DONUT_SIZE - icon_size) // 2
            if diff.ap_count == diff.all_count:
                all_ap_img = Image.open(ALL_AP_ICON).resize((icon_size, icon_size))
                donut_img.paste(all_ap_img, (icon_x, icon_y), all_ap_img)
            elif diff.fc_count == diff.all_count:
                all_fc_img = Image.open(ALL_FC_ICON).resize((icon_size, icon_size))
                donut_img.paste(all_fc_img, (icon_x, icon_y), all_fc_img)

            card_container.paste(donut_img, (donut_x, donut_y), donut_img)

            # --- Draw counts panel inside the white card ---
            # Counts panel is placed in the remaining area to the right of the donut.
            count_panel_x = donut_x + DONUT_SIZE + DONUT_PADDING
            content_area_right = content_area_x + content_area_width
            count_panel_width = content_area_right - count_panel_x - DONUT_PADDING
            count_panel_height = DONUT_SIZE  # keep same as donut for visual balance
            count_img = Image.new(
                "RGBA", (count_panel_width, count_panel_height), (255, 255, 255, 0)
            )
            count_draw = ImageDraw.Draw(count_img)
            count_draw.rounded_rectangle(
                (0, 0, count_panel_width, count_panel_height),
                radius=CARD_RADIUS,
                fill="#38383adf",
            )

            labels = ["ALL PERFECT", "FULL COMBO", "CLEAR", "ALL"]
            total_text_height = (text_height * 4) + (line_spacing * 3)
            start_y = (count_panel_height - total_text_height) // 2

            for idx, label in enumerate(labels):
                y_pos = start_y + idx * (text_height + line_spacing)
                count_draw.text(
                    (COUNT_PADDING_X, y_pos),
                    label,
                    fill=COUNT_FONT_COLOR,
                    font=COUNT_FONT_CATEGORIES,
                )
                if label == "ALL PERFECT":
                    value = str(diff.ap_count)
                elif label == "FULL COMBO":
                    value = str(diff.fc_count)
                elif label == "CLEAR":
                    value = str(diff.clear_count)
                elif label == "ALL":
                    value = str(diff.all_count)
                count_draw.text(
                    (count_panel_width - COUNT_PADDING_X, y_pos),
                    value,
                    fill=COUNT_FONT_COLOR,
                    font=COUNT_FONT_TEXT,
                    anchor="ra",
                )

            card_container.alpha_composite(count_img, (count_panel_x, donut_y))

            # Composite the white card (with donut and counts) into the main image.
            new_im.alpha_composite(card_container, (CARD_GUTTER_WIDTH, y_card))

            # --- Now paste the badge on top so it overlaps all else ---
            diff_key = diff.difficulty.lower()
            base_img = difficulty_images.get(diff_key)
            if base_img:
                if diff_key == "append":
                    top_color = base_img.getpixel((1, 1))
                    bottom_color = base_img.getpixel((CARD_WIDTH - 1, DONUT_SIZE - 1))
                    badge_bg = Image.new("RGB", (max_badge_width, max_badge_height))
                    draw_gradient(badge_bg, top_color, bottom_color)
                else:
                    base_color = base_img.getpixel((1, 1))
                    badge_bg = Image.new(
                        "RGB", (max_badge_width, max_badge_height), base_color
                    )
            else:
                badge_bg = Image.new("RGB", (max_badge_width, max_badge_height), "gray")
            badge_bg = badge_bg.convert("RGB")
            badge_mask = Image.new("L", (max_badge_width, max_badge_height), 0)
            mask_draw = ImageDraw.Draw(badge_mask)
            mask_draw.rounded_rectangle(
                (0, 0, max_badge_width, max_badge_height),
                radius=(max_badge_height // 2),
                fill=255,
            )
            badge_x = CARD_GUTTER_WIDTH + (CARD_WIDTH - max_badge_width) // 2
            badge_y = y_card - 20
            new_im.paste(badge_bg, (badge_x, badge_y), badge_mask)
            # Draw badge text centered in the badge.
            badge_text = diff.difficulty.upper()
            text_w = badge_font.getlength(badge_text)
            text_bbox = badge_font.getbbox(badge_text)
            text_h = text_bbox[3] - text_bbox[1]
            text_x = badge_x + (max_badge_width - text_w) / 2
            text_y = badge_y + (max_badge_height - text_h) / 2 - 5
            im_draw.text((text_x, text_y), badge_text, fill="black", font=badge_font)

        obj = BytesIO()
        new_im.save(obj, "PNG")
        obj.seek(0)
        return obj

    return main(data)


def generate_progress(data: list, difficulty: str):
    FONTPATH = "DATA/data/ASSETS/rodinntlg_eb.otf"
    FONTPATH_LIGHT = "DATA/data/ASSETS/rodinntlg_m.otf"

    IMAGE_WIDTH = 2000
    HEADER_HEIGHT = 200
    SUB_HEADER_HEIGHT = 100
    CARD_HEIGHT = 400
    CARD_GUTTER_HEIGHT = 50
    CARD_GUTTER_WIDTH = 50
    CARD_WIDTH = (IMAGE_WIDTH - (CARD_GUTTER_WIDTH * 3)) // 2
    CARD_RADIUS = 25

    # relative to the card
    CIRCLE_RADIUS = 70
    CIRCLE_X = CIRCLE_RADIUS  # the center of the circle
    CIRCLE_Y = CARD_HEIGHT // 2
    CIRCLE_DIAMETER = CIRCLE_RADIUS * 2

    CIRCLE_TEXT_OFFSET_X = 1.3
    CIRCLE_TEXT_OFFSET_Y = 1.74
    CIRCLE_FONTSIZE = 75
    CIRCLE_FONT = ImageFont.truetype(FONTPATH, CIRCLE_FONTSIZE)

    CIRCLE_TEXT_COLOR = "black"

    DONUT_THICKNESS = 75
    DONUT_PADDING = 30

    FC_COLOR = "#e83ce3"
    CLEAR_COLOR = "#F9D442"
    NOT_CLEAR_COLOR = "#38383a"

    ALL_AP_ICON = "DATA/data/ASSETS/normal_ap.png"
    ALL_FC_ICON = "DATA/data/ASSETS/normal_fc.png"
    ICON_PADDING = 20

    BACKGROUND_IMG = "DATA/data/ASSETS/hug.png"

    COUNT_PADDING_Y = 47
    COUNT_PADDING_X = 30
    COUNT_SPACING = 85
    COUNT_BACKGROUND_COLOR = "#38383adf"
    COUNT_FONTSIZE = 50
    COUNT_FONT_CATEGORIES = ImageFont.truetype(FONTPATH, COUNT_FONTSIZE)

    COUNT_FONT_COLOR = "white"
    COUNT_FONT_TEXT = ImageFont.truetype(FONTPATH_LIGHT, COUNT_FONTSIZE)

    difficulty_colors = {
        "append": "DATA/data/ASSETS/append_color.jpg",
        "hard": "DATA/data/ASSETS/hard_color.jpg",
        "normal": "DATA/data/ASSETS/normal_color.jpg",
        "easy": "DATA/data/ASSETS/easy_color.jpg",
        "master": "DATA/data/ASSETS/master_color.jpg",
        "expert": "DATA/data/ASSETS/expert_color.jpg",
    }

    difficulty_images = {
        key: Image.open(path)
        .resize((CARD_WIDTH, CARD_HEIGHT), Image.LANCZOS)
        .convert("RGBA")
        for key, path in difficulty_colors.items()
    }

    def main(data: list[DifficultyCategory]):
        number_of_cards = len(data)
        # two cards per row
        number_of_rows = ceil(number_of_cards / 2)
        total_height = (
            HEADER_HEIGHT
            + SUB_HEADER_HEIGHT
            + (number_of_rows * CARD_HEIGHT)
            + ((number_of_rows + 1) * CARD_GUTTER_HEIGHT)
        )

        new_im = Image.new("RGBA", (IMAGE_WIDTH, total_height))

        # draw background image
        background_img = Image.open(BACKGROUND_IMG)
        original_width, original_height = background_img.size
        if original_height > total_height:
            background_img = background_img.crop((0, 0, original_width, total_height))
        else:
            background_img = background_img.resize((original_width, total_height))

        background_img = background_img.resize((IMAGE_WIDTH, total_height))
        new_im.paste(background_img, (0, 0))

        im_draw = ImageDraw.Draw(new_im)

        # Top bar
        im_draw.rectangle(
            [(0, 0), (new_im.width, HEADER_HEIGHT)], fill="#b4ccfa", outline="#00194a"
        )

        # Top-left text
        font = ImageFont.truetype(FONTPATH, 96)
        im_draw.text((20, 28), "Your PJSK Progress", fill="black", font=font)
        watermark = ImageFont.truetype(FONTPATH, 60)
        im_draw.text((20, 130), "Generated by Sbotga", fill="black", font=watermark)

        right_text = difficulty.upper()
        right_text_width = font.getlength(right_text)

        image_width, image_height = im_draw.im.size
        x_position = int(image_width - right_text_width - 20)

        def draw_gradient(img, start, end):
            px = img.load()
            for y in range(0, img.height):
                color = tuple(
                    int(start[i] + (end[i] - start[i]) * y / img.height)
                    for i in range(3)
                )
                for x in range(0, img.width):
                    px[x, y] = color

        difficulty_img = difficulty_images[difficulty]
        top_left_color = difficulty_img.getpixel((1, 1))
        bottom_right_color = difficulty_img.getpixel((CARD_WIDTH - 1, CARD_HEIGHT - 1))
        w, h = font.getbbox(right_text)[2:]
        gradient = Image.new("RGB", (w, h))
        draw_gradient(gradient, top_left_color, bottom_right_color)
        im_text = Image.new("RGBA", (w, h))
        d = ImageDraw.Draw(im_text)
        d.text((0, 0), right_text, font=font)
        new_im.paste(gradient, (x_position, 53), im_text)

        for i, diff in enumerate(data):
            data_img = Image.new(
                "RGBA", (CARD_WIDTH, CARD_HEIGHT), color=(255, 255, 255, 0)
            )
            draw = ImageDraw.Draw(data_img)

            # card rectangle
            draw.rounded_rectangle(
                (CIRCLE_RADIUS, 0, CARD_WIDTH, CARD_HEIGHT), radius=25, fill="white"
            )

            # circle with text in the middle
            gradient = Image.new("RGB", (CIRCLE_RADIUS * 2, CIRCLE_RADIUS * 2))
            draw_gradient(gradient, top_left_color, bottom_right_color)
            im_mask = Image.new("L", (CIRCLE_RADIUS * 2, CIRCLE_RADIUS * 2), 0)
            d_mask = ImageDraw.Draw(im_mask)
            d_mask.ellipse((0, 0, CIRCLE_RADIUS * 2, CIRCLE_RADIUS * 2), fill=255)

            ellipse_gradient = Image.composite(
                gradient,
                Image.new("RGB", (CIRCLE_RADIUS * 2, CIRCLE_RADIUS * 2), (0, 0, 0)),
                im_mask,
            )

            data_img.paste(
                ellipse_gradient,
                (CIRCLE_X - CIRCLE_RADIUS, CIRCLE_Y - CIRCLE_RADIUS),
                im_mask,
            )

            draw.text(
                (
                    CIRCLE_X
                    - (CIRCLE_RADIUS / CIRCLE_TEXT_OFFSET_X)
                    + (2 if len(str(diff.difficulty)) == 2 else 28),
                    CIRCLE_Y - (CIRCLE_RADIUS / CIRCLE_TEXT_OFFSET_Y) + 4,
                ),
                str(diff.difficulty),
                fill=CIRCLE_TEXT_COLOR,
                font=CIRCLE_FONT,
            )

            # donut chart
            donut_width = CARD_HEIGHT - (DONUT_PADDING * 2)
            donut_img = Image.new(
                "RGBA", (donut_width, donut_width), color=(255, 255, 255, 0)
            )

            # draw pie chart
            aped = diff.ap_count
            fced = diff.fc_count - diff.ap_count
            cleared = diff.clear_count - diff.fc_count
            not_cleared = diff.all_count - diff.clear_count

            percentage_ap = aped / diff.all_count
            percentage_fc = fced / diff.all_count
            percentage_clear = cleared / diff.all_count
            percentage_not_clear = not_cleared / diff.all_count

            angle_ap = percentage_ap * 360
            angle_fc = angle_ap + (percentage_fc * 360)
            angle_clear = angle_fc + (percentage_clear * 360)
            angle_not_clear = angle_clear + (percentage_not_clear * 360)

            donut_draw = ImageDraw.Draw(donut_img)
            pie_location = (0, 0, donut_width, donut_width)
            donut_draw.pieslice(pie_location, 0, 360, fill="white")

            ap_color_sample = Image.open(ALL_AP_ICON)

            # Get the top and bottom colors
            color_top = ap_color_sample.getpixel((ap_color_sample.size[0] // 2, 60))
            color_bottom = ap_color_sample.getpixel(
                (ap_color_sample.size[0] // 2, ap_color_sample.size[1] - 60)
            )

            gradient = Image.new("RGB", (donut_width, donut_width))
            draw_gradient(gradient, color_top, color_bottom)

            # Create the mask for the pie slice
            im_mask = Image.new(
                "L", (donut_width, donut_width), 0
            )  # Single-channel (grayscale) mask
            d_mask = ImageDraw.Draw(im_mask)
            d_mask.pieslice(
                (0, 0, donut_width, donut_width), 0, angle_ap, fill=255
            )  # Fill the slice with white
            # Paste the gradient onto the donut image using the mask
            donut_img.paste(gradient, pie_location[:2], im_mask)

            donut_draw.pieslice(pie_location, angle_ap, angle_fc, fill=FC_COLOR)
            donut_draw.pieslice(pie_location, angle_fc, angle_clear, fill=CLEAR_COLOR)
            donut_draw.pieslice(
                pie_location, angle_clear, angle_not_clear, fill=NOT_CLEAR_COLOR
            )

            # erase the middle to make it a donut
            donut_draw.ellipse(
                (
                    DONUT_THICKNESS,
                    DONUT_THICKNESS,
                    CARD_HEIGHT - DONUT_THICKNESS - (DONUT_PADDING * 2),
                    CARD_HEIGHT - DONUT_THICKNESS - (DONUT_PADDING * 2),
                ),
                fill="white",
            )

            # if it's all APed or all FCed, draw icon in the middle
            icon_size = (
                donut_width
                - (DONUT_THICKNESS * 2)
                - (DONUT_PADDING * 2)
                - (ICON_PADDING * 2)
            )
            icon_x = (donut_width - icon_size) // 2
            icon_y = (donut_width - icon_size) // 2
            if diff.ap_count == diff.all_count:
                all_ap_img = Image.open(ALL_AP_ICON)
                all_ap_img = all_ap_img.resize((icon_size, icon_size))
                donut_img.paste(all_ap_img, (icon_x, icon_y), all_ap_img)
            elif diff.fc_count == diff.all_count:
                all_fc_img = Image.open(ALL_FC_ICON)
                all_fc_img = all_fc_img.resize((icon_size, icon_size))
                donut_img.paste(all_fc_img, (icon_x, icon_y), all_fc_img)

            data_img.paste(
                donut_img,
                ((CIRCLE_RADIUS * 2) + DONUT_PADDING, DONUT_PADDING),
                donut_img,
            )

            # counts in the right
            count_width = (
                CARD_WIDTH - (CIRCLE_RADIUS * 2) - donut_width - DONUT_PADDING * 2
            )
            count_img = Image.new(
                "RGBA", (count_width, CARD_HEIGHT), color=(255, 255, 255, 0)
            )
            count_draw = ImageDraw.Draw(count_img)
            # only round the right side
            count_draw.rounded_rectangle(
                (0, 0, count_width, CARD_HEIGHT), radius=25, fill=COUNT_BACKGROUND_COLOR
            )
            count_draw.rectangle(
                (0, 0, count_width / 2, CARD_HEIGHT), fill=COUNT_BACKGROUND_COLOR
            )

            ap_pos = (COUNT_PADDING_X, COUNT_PADDING_Y)
            fc_pos = (COUNT_PADDING_X, COUNT_PADDING_Y + COUNT_SPACING)
            clear_pos = (COUNT_PADDING_X, COUNT_PADDING_Y + COUNT_SPACING * 2)
            all_pos = (COUNT_PADDING_X, COUNT_PADDING_Y + COUNT_SPACING * 3)

            count_draw.text(
                ap_pos, "AP", fill=COUNT_FONT_COLOR, font=COUNT_FONT_CATEGORIES
            )
            count_draw.text(
                fc_pos, "FC", fill=COUNT_FONT_COLOR, font=COUNT_FONT_CATEGORIES
            )
            count_draw.text(
                clear_pos, "CLEAR", fill=COUNT_FONT_COLOR, font=COUNT_FONT_CATEGORIES
            )
            count_draw.text(
                all_pos, "ALL", fill=COUNT_FONT_COLOR, font=COUNT_FONT_CATEGORIES
            )

            count_draw.text(
                (count_width - COUNT_PADDING_X, ap_pos[1]),
                str(diff.ap_count),
                fill=COUNT_FONT_COLOR,
                font=COUNT_FONT_TEXT,
                anchor="ra",
            )
            count_draw.text(
                (count_width - COUNT_PADDING_X, fc_pos[1]),
                str(diff.fc_count),
                fill=COUNT_FONT_COLOR,
                font=COUNT_FONT_TEXT,
                anchor="ra",
            )
            count_draw.text(
                (count_width - COUNT_PADDING_X, clear_pos[1]),
                str(diff.clear_count),
                fill=COUNT_FONT_COLOR,
                font=COUNT_FONT_TEXT,
                anchor="ra",
            )
            count_draw.text(
                (count_width - COUNT_PADDING_X, all_pos[1]),
                str(diff.all_count),
                fill=COUNT_FONT_COLOR,
                font=COUNT_FONT_TEXT,
                anchor="ra",
            )

            data_img.alpha_composite(count_img, (CARD_WIDTH - count_width, 0))

            x_location = (
                CARD_GUTTER_WIDTH if i % 2 == 0 else CARD_WIDTH + CARD_GUTTER_WIDTH * 2
            )
            y_location = (
                HEADER_HEIGHT
                + SUB_HEADER_HEIGHT
                + CARD_GUTTER_HEIGHT
                + (i // 2) * (CARD_HEIGHT + CARD_GUTTER_HEIGHT)
            )
            new_im.alpha_composite(data_img, (x_location, y_location))

        obj = BytesIO()
        new_im.save(obj, "PNG")
        obj.seek(0)
        return obj

    return main(data)
