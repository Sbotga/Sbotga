def generate_progress_bar(
    old_current: int, new_current: int, out_of: int, bar_length: int = 10
) -> str:
    """Generate a progress bar showing old progress, new progress, and remaining progress with customizable bar length."""
    total_progress = new_current / out_of  # This gives a value between 0 and 1
    filled_length = int(
        bar_length * total_progress
    )  # How many segments should be filled

    # Calculate the split between old and new progress
    old_filled_length = int(
        bar_length * (old_current / out_of)
    )  # Old progress segments

    # Generate the progress bar with three segments
    progress_bar = (
        "🟩" * old_filled_length  # Old progress (green)
        + "🟨" * (filled_length - old_filled_length)  # New progress (yellow)
        + "🟥" * (bar_length - filled_length)  # Remaining progress (red)
    )

    return progress_bar
