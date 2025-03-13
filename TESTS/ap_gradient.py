from PIL import Image, ImageDraw, ImageColor

# Image dimensions
width, height = 1024, 1024

# Hex colors
start_color_hex = "#7857ff"  # #7857ff (purple)
end_color_hex = "#fcacf7"  # #fcacf7 (pink)

# Convert hex to RGB
start_color = ImageColor.getrgb(start_color_hex)
end_color = ImageColor.getrgb(end_color_hex)

# Create a new image with RGB mode
image = Image.new("RGB", (width, height), (255, 255, 255))  # White background
draw = ImageDraw.Draw(image)

# Generate the gradient
for y in range(height):
    # Interpolate between the two colors for each pixel row
    r = int(start_color[0] + (end_color[0] - start_color[0]) * y / height)
    g = int(start_color[1] + (end_color[1] - start_color[1]) * y / height)
    b = int(start_color[2] + (end_color[2] - start_color[2]) * y / height)

    # Draw the line for this gradient row
    draw.line((0, y, width, y), fill=(r, g, b))

# Add a white border
draw.rectangle([0, 0, width, height], outline="white", width=2)

# Save the image as a JPG
image.save("gradient_image.jpg", "JPEG")
