import sys
import os
import base64


def generate_font_bytes(font_path):
    """Generates the byte data for pasting into your script."""
    if not os.path.exists(font_path):
        print(f"Error: The font file at '{font_path}' does not exist.")
        return

    with open(font_path, "rb") as font_file:
        font_data = font_file.read()

    # Convert the byte data to a Python str and print it
    byte_data_str = base64.b64encode(font_data).decode()
    with open("results.txt", "w") as f:
        f.write(byte_data_str)
    print('font = b"(stuff in results.txt)"')


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_font_bytes.py <font_file_path>")
    else:
        font_file = sys.argv[1]
        generate_font_bytes(font_file)
