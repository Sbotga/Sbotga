import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

import aiohttp
import requests

import numpy as np

import pyperclip

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi import Request, WebSocket, WebSocketDisconnect
import uvicorn

from PIL import Image, ImageDraw, ImageFont, ImageOps

from io import BytesIO
import asyncio, threading, os, json, sys, time, wave
from base64 import b64encode

config_file = "configs.json"
debug = True  # TODO

# Determine if running as a bundled app
if getattr(sys, "frozen", False):  # If the app is frozen (PyInstaller or Nuitka)
    # Access the bundled path
    config_file = os.path.join(sys._MEIPASS, config_file)
else:
    # Normal case when running in the source directory
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)

if not os.path.exists(config_file):
    default_config = {"port": 3939, "proxy_port": 4000, "hidden": False}
    with open(config_file, "w", encoding="utf8") as f:
        json.dump(default_config, f, indent=4)

with open(config_file, "r", encoding="utf8") as f:
    config = json.load(f)


def save_config():
    with open(config_file, "w", encoding="utf8") as f:
        json.dump(config, f, indent=4)


def is_valid_port(port):
    try:
        # Check if the port is a valid integer and within the valid range
        port_num = int(port)
        if 1024 <= port_num <= 65535:
            return True
        else:
            return False
    except ValueError:
        return False


class CurrentlyPlayingApp:
    def __init__(self, root: tk.Tk):
        self.loop = None
        self.root = root
        self.root.title("PJSK Currently Playing Config")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        self.image_base64 = None

        self.device_map = {}  # Maps display name to device index
        self.websockets = {}
        self.task_futures = None
        self.hidden = config.get("hidden", False)
        self.process = None

        class E:
            def __init__(self):
                self.started = False

        self.fastapi_server = E()
        self.server_port = tk.IntVar(value=config.get("port", 3939))  # Default port
        self.proxy_port = tk.IntVar(value=config.get("port", 4000))  # Default port

        # UI Components
        self.create_widgets()

        # Start the asyncio loop in a separate thread
        self.loop_thread = threading.Thread(target=self.run_asyncio_loop)
        self.loop_thread.daemon = (
            True  # This makes the thread exit when the main program exits
        )
        self.loop_thread.start()

    def run_asyncio_loop(self):
        """Runs an asyncio event loop in a separate thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)  # Set a new event loop for this thread
        self.loop.run_forever()  # Run the loop indefinitely

    def create_widgets(self):
        # Styling
        style = ttk.Style()
        style.configure(
            "TButton", padding=6, relief="flat", borderwidth=2, focuscolor="none"
        )
        style.configure("TCombobox", padding=6, relief="flat")
        style.configure("TLabel", padding=5)


        # Buttons for monitoring control
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)

        self.start_button = ttk.Button(
            self.button_frame, text="Start Monitoring", command=self.start_monitoring
        )
        self.start_button.pack(side="left", padx=10)

        self.stop_button = ttk.Button(
            self.button_frame,
            text="Stop Monitoring",
            command=self.stop_monitoring,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=10)

        # Port configuration
        self.port_label = ttk.Label(self.root, text="Server Port:")
        self.port_label.pack(pady=5)

        # Create a frame to hold the entry and button side by side
        port_frame = tk.Frame(self.root)
        port_frame.pack(pady=5)

        # Port entry field
        self.port_entry = ttk.Entry(port_frame, textvariable=self.server_port, width=15)
        self.port_entry.pack(side="left", padx=5)

        # Change Ports button
        self.server_button = ttk.Button(
            port_frame, text="Change Port", command=self.restart_server
        )
        self.server_button.pack(side="left")

        # Port configuration
        self.proxy_port_label = ttk.Label(self.root, text="Proxy Port:")
        self.proxy_port_label.pack(pady=5)

        # Create a frame to hold the entry and button side by side
        proxy_port_frame = tk.Frame(self.root)
        proxy_port_frame.pack(pady=5)

        # Port entry field
        self.proxy_port_entry = ttk.Entry(proxy_port_frame, textvariable=self.proxy_port, width=15)
        self.proxy_port_entry.pack(side="left", padx=5)

        # Change Ports button
        self.proxy_button = ttk.Button(
            port_frame, text="Change Port", command=self.start_proxy
        )
        self.server_button.pack(side="left")

        # Browser Source Link
        self.link_label = ttk.Label(self.root, text="Browser Source Link:")
        self.link_label.pack(pady=5)

        link_frame = tk.Frame(self.root)
        link_frame.pack(pady=5)

        self.link_entry = ttk.Entry(link_frame, width=50, state="readonly")
        self.link_entry.pack(side="left", padx=5)

        self.copy_button = ttk.Button(
            link_frame, text="Copy Link", command=self.copy_link
        )
        self.copy_button.pack(side="left", padx=5)

        # Create the button
        self.toggle_button = ttk.Button(
            self.root, text="Hide Source", command=self.toggle_source, state="disabled"
        )
        self.toggle_button.pack(pady=10)
        if self.hidden:
            self.toggle_button.config(text="Unhide Source")
        else:
            self.toggle_button.config(text="Hide Source")

    async def generate_image(self, url: str = None, song_name: str = None):
        BASE_URL = "https://pjsk.econuker.xyz/font/"

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}rodinntlg_eb") as response:
                if response.status != 200:
                    raise Exception(
                        f"Failed to fetch font rodinntlg_eb: {response.status}"
                    )
                top_font = await response.read()
            async with session.get(f"{BASE_URL}rodinntlg_m") as response:
                if response.status != 200:
                    raise Exception(
                        f"Failed to fetch font rodinntlg_m: {response.status}"
                    )
                bottom_font = await response.read()

        background_color = "#626282"
        border_color = "#000000"
        border_width = 15  # Slightly thicker border
        rounded_corner_radius = 30  # Increase radius to round corners more
        max_width = 950
        padding = 20
        img_size = (500, 500)

        # Fetch image if URL is provided or create a default blank square if not
        if url:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    img_data = await response.read()
            img = Image.open(BytesIO(img_data))
        else:
            img = Image.new("RGB", img_size, color="#d3d3d3")

        # Load fonts from byte data using Pillow
        top_font = ImageFont.truetype(BytesIO(top_font), 60)
        bottom_font = ImageFont.truetype(BytesIO(bottom_font), 45)

        # Create a blank canvas for the editor
        editor = Image.new("RGB", (1024, 1024), color=background_color)
        draw = ImageDraw.Draw(editor)

        img_x = (1024 - img.size[0]) // 2
        img_y = (1024 - img.size[1]) // 2
        editor.paste(
            self.add_rounded_corners(img, rounded_corner_radius), (img_x, img_y)
        )

        bottom_text = "No Song Found" or song_name

        # Wrap the text if it exceeds max width
        wrapped_text = self.wrap_text(
            bottom_text, bottom_font, max_width - 2 * padding, draw
        )

        top_text = "Currently Playing"
        text_bbox = draw.textbbox((0, 0), top_text, font=top_font)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text(
            ((1024 - text_width) / 2, img_y - 150),
            top_text,
            font=top_font,
            fill="#ffffff",
        )

        # Calculate text height and position it centered right under the image
        text_bbox = draw.textbbox(
            (0, 0), wrapped_text, font=bottom_font
        )  # Use textbbox for bounding box
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        draw.text(
            ((1024 - text_width) / 2, img_y + img.size[1] + 40),
            wrapped_text,
            font=bottom_font,
            fill="#ffffff",
        )  # Move below image and make text white

        # Add a thin black border around the image
        editor = self.add_border(editor, border_width, border_color)

        # Round corners of the image and the background
        rounded_img = self.add_rounded_corners(editor, rounded_corner_radius)

        # Save the final image in PNG format
        img_b64 = BytesIO()
        rounded_img.save(img_b64, format="PNG")  # Specify format as PNG
        return b64encode(img_b64.getvalue()).decode()

    def wrap_text(self, text, font, max_width, draw):
        lines = []
        words = text.split(" ")
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if draw.textbbox((0, 0), test_line, font=font)[2] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return "\n".join(lines)

    def calculate_text_height(self, text, font, draw):
        lines = text.split("\n")
        return len(lines) * draw.textbbox((0, 0), "A", font=font)[3]

    def add_border(self, img, border_width, border_color):
        return ImageOps.expand(img, border=border_width, fill=border_color)

    def add_rounded_corners(self, img, radius):
        width, height = img.size
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, width, height], radius, fill=255)
        img.putalpha(mask)
        return img

    def toggle_source(self):
        self.hidden = not self.hidden
        config["hidden"] = self.hidden
        save_config()

        if self.hidden:
            self.toggle_button.config(text="Unhide Source")
        else:
            self.toggle_button.config(text="Hide Source")

        async def the_task():
            if self.hidden:
                await self.send_image_update_request("hide")
            else:
                await self.send_image_update_request("show")

        asyncio.run_coroutine_threadsafe(the_task(), self.loop)

    def stop_monitoring(self):
        try:
            if not self.running:
                return
            self.running = False
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.stop_proxy()
        except:
            pass

    async def send_image_update_request(self, action: str, b64: str = None):

        if self.image_base64 == None:
            self.image_base64 = await self.generate_image(url=, song_name=)

        for websocket in self.websockets.values():
            try:
                message = {"action": action}
                if action == "update":
                    message["url"] = f"data:image/png;base64,{b64 or self.image_base64}"
                elif action == "hide":
                    pass
                elif action == "show":
                    message["url"] = f"data:image/png;base64,{b64 or self.image_base64}"
                await websocket.send_json(message)
            except:
                pass

    def start_server(self):
        """Start the FastAPI server."""
        try:
            if not is_valid_port(self.server_port.get()):
                raise KeyError("Port must be between 1024-65535")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server: {e}")
            self.root.destroy()
        app = FastAPI()

        @app.get("/")
        async def root():
            return {"message": "normal"}

        @app.get("/stop")
        async def stop():
            try:
                await self.fastapi_server.shutdown()
            except (asyncio.exceptions.CancelledError, asyncio.exceptions.TimeoutError):
                pass

        @app.get("/bsrc", response_class=HTMLResponse)
        async def serve_html(request: Request):
            """
            Serve an HTML page for the specific user and image source.
            """
            if "OBS/" not in request.headers.get("User-Agent", "") and not debug:
                return HTMLResponse(
                    content="""<p>Cannot access in browser. This is a OBS-type browser source.</p>"""
                )

            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{
                        margin: 0;
                        background: rgba(0, 0, 0, 0); /* Fully transparent */
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        flex-direction: column;
                        position: relative;
                    }}
                    img {{
                        max-width: 100%;
                        max-height: 100%;
                        opacity: 1; /* Default to visible */
                        transition: opacity 0.5s ease-in-out; /* Smooth fade for visibility */
                        position: relative; /* Position context for watermark */
                    }}
                    .hidden {{
                        opacity: 0; /* Fully transparent */
                    }}
                    .watermark {{
                        position: absolute;
                        bottom: 10px;
                        right: 10px;
                        background-color: rgba(255, 255, 255, 0.8);
                        border-radius: 25px;
                        padding: 10px 20px;
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        font-size: 16px;
                        text-align: center;
                        display: none; /* Hidden by default */
                    }}
                    .watermark.show {{
                        display: block; /* Show when necessary */
                    }}
                </style>
            </head>
            <body>
                <img id="image" src alt="Dynamic Image">
                <!-- <div class="watermark" id="watermark">PJSK Twitch Bot by YumYummity</div> -->
                <script>
                    const img = document.getElementById("image");
                    const watermark = document.getElementById("watermark");
                    let reconnectAttempts = 0;
                    const maxReconnectAttempts = 999999999; // If page refreshes, the source needs to be refreshed manually as well.
                    let heartbeatInterval;
                    
                    function connectWebSocket() {{
                        const ws = new WebSocket("ws://localhost:{self.server_port.get()}/ws");

                        ws.onmessage = (event) => {{
                            reconnectAttempts = 0; // Reset reconnect attempts on a successful message
                            const data = JSON.parse(event.data);

                            console.log(data);

                            if (data.action === "update") {{
                                img.src = data.url;
                                img.classList.remove("hidden");
                                // watermark.classList.add("show"); // Show watermark when image is updated
                            }} else if (data.action === "hide") {{
                                img.classList.add("hidden");
                                // watermark.classList.remove("show"); // Hide watermark when image is hidden
                            }} else if (data.action === "show") {{
                                img.classList.remove("hidden");
                                img.src = data.url;
                                // watermark.classList.add("show"); // Show image and watermark when triggered
                            }}
                        }};

                        ws.onopen = () => {{
                            console.log("WebSocket connection established.");
                            reconnectAttempts = 0;

                            // Start the heartbeat
                            clearInterval(heartbeatInterval); // Ensure no duplicate intervals
                            heartbeatInterval = setInterval(() => {{
                                console.log("Sending ping...");
                                ws.send(JSON.stringify({{ action: "ping" }}));
                            }}, 20000); // 20 seconds
                        }};
                        
                        ws.onclose = () => {{
                            reconnectAttempts++;
                            if (reconnectAttempts <= maxReconnectAttempts) {{
                                console.warn(`WebSocket closed. Attempting to reconnect... (${{reconnectAttempts}})`);
                                setTimeout(connectWebSocket, 3000); // Retry after 3 seconds
                            }} else {{
                                console.error("Max reconnect attempts reached. Reloading page.");
                                location.reload(); // Reload the page after failed reconnect attempts
                            }}
                        }};

                        ws.onerror = (error) => {{
                            console.error("WebSocket error:", error);
                            ws.close();
                        }};
                    }}

                    // Start WebSocket connection
                    connectWebSocket();
                </script>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """
            Handle WebSocket connections for a specific user and image source.
            """

            await websocket.accept()

            def get_next_available_key(d):
                if not d:
                    return 0
                keys = sorted(d.keys())
                if keys[0] > 0:
                    return 0
                for i in range(len(keys) - 1):
                    if keys[i + 1] - keys[i] > 1:
                        return keys[i] + 1
                return keys[-1] + 1

            index = get_next_available_key(self.websockets)
            self.websockets[index] = websocket

            try:
                await self.send_image_update_request("update", self.image_base64)
                if self.hidden:
                    await self.send_image_update_request("hide")
                while True:
                    # Keep the connection alive; listen for client messages if needed
                    text = await websocket.receive_text()
                    if text == "ping":
                        await websocket.send_text("pong")
            except WebSocketDisconnect:
                pass
            finally:
                try:
                    await websocket.close()
                except RuntimeError:
                    pass
            self.websockets.pop(index)

        self.fastapi_server = uvicorn.Server(
            config=uvicorn.Config(
                app,
                host="0.0.0.0",
                port=self.server_port.get(),
                log_level="info",
                timeout_graceful_shutdown=0.2,
            )
        )
        threading.Thread(target=self.fastapi_server.run, daemon=True).start()

        self.link_entry.config(state="normal")
        self.toggle_button.config(state="normal")
        self.link_entry.delete(0, tk.END)
        self.link_entry.insert(0, f"http://localhost:{self.server_port.get()}/bsrc/")
        self.link_entry.config(state="readonly")

        try:
            res = requests.get(f"http://localhost:{self.server_port.get()}/", timeout=1)
            res.raise_for_status()
        except:
            messagebox.showerror(
                "Error", f"Failed to start server. Is the port in use?"
            )
            self.root.destroy()

    def restart_server(self):
        """Restart the FastAPI server."""
        self.server_button.config(state="disabled")
        try:
            if not is_valid_port(self.server_port.get()):
                raise KeyError("Port must be between 1024-65535")
            config["port"] = self.server_port.get()
            save_config()
            messagebox.showinfo("Server Port Changed", f"Restart app to use new port.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to change port: {e}")
        self.server_button.config(state="normal")

    def on_close(self):
        self.running = False
        if self.fastapi_server.started:
            try:
                requests.get(
                    f"http://localhost:{self.server_port.get()}/stop/", timeout=2
                )
            except:
                pass
        self.root.destroy()

    def copy_link(self):
        pyperclip.copy(self.link_entry.get())
        messagebox.showinfo("Copied", "Link copied to clipboard.")

    def start_monitoring(self):
        self.start_proxy()

    def stop_proxy(self):
        try:
            self.process.kill()
            self.process.terminate()
            self.process = None
        except:
            self.process = None

    def start_proxy(self):
        if self.process:
            self.stop_proxy()

# Main application
if __name__ == "__main__":
    root = tk.Tk()
    app = CurrentlyPlayingApp(root)
    app.start_server()  # Start the FastAPI server
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
