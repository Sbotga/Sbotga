donotload = False

from main import TwitchBot, DiscordBot

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from typing import Dict

router = APIRouter()
loaded = False


def setup():
    global loaded

    @router.get("/", response_class=HTMLResponse)
    async def serve_html(request: Request, id: str, n: int):
        """
        Serve an HTML page for the specific user and image source.
        """
        if (
            "OBS/" not in request.headers.get("User-Agent", "")
            and not request.app.debug
        ):
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
            <img id="image" src="https://via.placeholder.com/1200x800.png?text=Source+{n}" alt="Dynamic Image">
            <!-- <div class="watermark" id="watermark">PJSK Twitch Bot by YumYummity</div> -->
            <script>
                const img = document.getElementById("image");
                const watermark = document.getElementById("watermark");
                let reconnectAttempts = 0;
                const maxReconnectAttempts = 999999999; // If page refreshes, the source needs to be refreshed manually as well.
                let heartbeatInterval;
                
                function connectWebSocket() {{
                    const ws = new WebSocket("{request.app.ws_protocol}://{request.app.url}/user/{id}/bsrc/{n}/ws");

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

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, id: str, n: int):
        """
        Handle WebSocket connections for a specific user and image source.
        """
        bot: TwitchBot = websocket.app.twitch_bot  # Access the bot instance
        active_connections = (
            websocket.app.active_connections
        )  # Use the bot's active connections

        user_key = f"user_{id}"
        await websocket.accept()

        # Ensure the user key exists in active_connections
        if user_key not in active_connections:
            active_connections[user_key] = {}
        active_connections[user_key][n] = active_connections[user_key].get(n, [])
        active_connections[user_key][n].append(websocket)
        index = len(active_connections[user_key][n]) - 1

        try:
            c = await bot.user_data.get_display(id, n)
            await bot.send_image_update(bot, id, n, "update", c["url"])
            if c["hidden"]:
                await bot.send_image_update(bot, id, n, "hide")
            while True:
                # Keep the connection alive; listen for client messages if needed
                text = await websocket.receive_text()
                if text == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            # Handle disconnection
            del active_connections[user_key][n][index]
            if not active_connections[user_key][n]:
                del active_connections[user_key][n]
            if not active_connections[user_key]:
                del active_connections[user_key]
        finally:
            try:
                await websocket.close()
            except RuntimeError:
                pass
