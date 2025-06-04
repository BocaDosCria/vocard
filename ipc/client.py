import aiohttp
import asyncio
import logging
import function as func
import time
from dataclasses import dataclass
from typing import Optional, Dict

from discord.ext import commands

from .methods import process_methods

@dataclass
class ConnectionMetrics:
    """Track connection health and performance metrics."""
    connect_attempts: int = 0
    last_connect_time: Optional[float] = None
    reconnect_count: int = 0
    message_count: int = 0
    last_heartbeat: Optional[float] = None

class IPCClient:
    def __init__(
        self,
        bot: commands.Bot,
        host: str,
        port: int,
        password: str,
        heartbeat: int = 30,
        secure: bool = False,
        max_reconnect_attempts: int = 5,
        reconnect_delay: int = 5,
        *arg,
        **kwargs
    ) -> None:
        
        self._bot: commands.Bot = bot
        self._host: str = host
        self._port: int = port
        self._password: str = password
        self._heartbeat: int = heartbeat
        self._is_secure: bool = secure
        self._is_connected: bool = False
        self._is_connecting: bool = False
        self._max_reconnect_attempts: int = max_reconnect_attempts
        self._reconnect_delay: int = reconnect_delay
        self._logger: logging.Logger = logging.getLogger("ipc_client")
        
        self._websocket_url: str = f"{'wss' if self._is_secure else 'ws'}://{self._host}:{self._port}/ws_bot"
        self._session: Optional[aiohttp.ClientSession] = None
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._task: Optional[asyncio.Task] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        
        # Connection metrics and health tracking
        self._metrics = ConnectionMetrics()
        self._reconnect_lock = asyncio.Lock()

        # Fixed typo: _heanders -> _headers
        self._headers = {
            "Authorization": self._password,
            "User-Id": str(bot.user.id),
            "Client-Version": func.settings.version
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with proper cleanup."""
        await self.disconnect()

    async def _create_session(self) -> aiohttp.ClientSession:
        """Create optimized HTTP session with connection pooling."""
        if not self._connector:
            self._connector = aiohttp.TCPConnector(
                limit=10,  # Total connection pool size
                limit_per_host=5,  # Per host limit
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
        
        timeout = aiohttp.ClientTimeout(
            total=30,
            connect=10,
            sock_read=10
        )
        
        return aiohttp.ClientSession(
            connector=self._connector,
            timeout=timeout,
            headers={"User-Agent": f"Vocard-Bot/{func.settings.version}"}
        )

    async def _listen(self) -> None:
        """Enhanced message listening with better error handling."""
        self._logger.info("Starting message listener")
        
        while self._is_connected:
            try:
                # Add timeout to prevent hanging
                msg = await asyncio.wait_for(
                    self._websocket.receive(), 
                    timeout=self._heartbeat + 10
                )
                
                self._logger.debug(f"Received Message: {msg.type} - {msg.data if hasattr(msg, 'data') else 'N/A'}")
                self._metrics.message_count += 1
                self._metrics.last_heartbeat = time.time()

                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = msg.json()
                        # Process message in background to avoid blocking listener
                        asyncio.create_task(
                            self._process_message_safely(data),
                            name=f"process_msg_{self._metrics.message_count}"
                        )
                    except Exception as e:
                        self._logger.error(f"Failed to parse message JSON: {e}")
                        
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self._logger.error(f"WebSocket error: {self._websocket.exception()}")
                    break
                    
                elif msg.type in [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]:
                    self._logger.info("WebSocket connection closed by server")
                    break
                    
            except asyncio.TimeoutError:
                self._logger.warning("Message receive timeout - checking connection health")
                if not self.is_connected:
                    break
                    
            except asyncio.CancelledError:
                self._logger.info("Message listener cancelled")
                break
                
            except Exception as e:
                self._logger.error(f"Unexpected error in message listener: {e}")
                break

        # Trigger reconnection if we exit the loop unexpectedly
        if self._is_connected:
            self._is_connected = False
            self._logger.info("Message listener ended - scheduling reconnection")
            asyncio.create_task(self._attempt_reconnection())

    async def _process_message_safely(self, data: dict) -> None:
        """Safely process incoming messages with error isolation."""
        try:
            await process_methods(self, self._bot, data)
        except Exception as e:
            self._logger.error(f"Error processing message: {e}", exc_info=True)

    async def _attempt_reconnection(self) -> None:
        """Handle automatic reconnection with exponential backoff."""
        async with self._reconnect_lock:
            if self._is_connected or self._is_connecting:
                return  # Already connected/connecting
                
            self._metrics.reconnect_count += 1
            
            for attempt in range(1, self._max_reconnect_attempts + 1):
                try:
                    delay = min(self._reconnect_delay * (2 ** (attempt - 1)), 60)  # Max 60s delay
                    self._logger.info(f"Reconnection attempt {attempt}/{self._max_reconnect_attempts} in {delay}s")
                    
                    await asyncio.sleep(delay)
                    await self.connect()
                    
                    if self._is_connected:
                        self._logger.info(f"Successfully reconnected after {attempt} attempts")
                        return
                        
                except Exception as e:
                    self._logger.error(f"Reconnection attempt {attempt} failed: {e}")
                    
            self._logger.error(f"Failed to reconnect after {self._max_reconnect_attempts} attempts")

    async def send(self, data: dict) -> bool:
        """Send data through WebSocket with enhanced error handling and validation."""
        if not isinstance(data, dict):
            self._logger.error("Data must be a dictionary")
            return False
            
        if not self.is_connected:
            self._logger.warning("WebSocket is not connected. Cannot send message.")
            return False

        try:
            await self._websocket.send_json(data)
            self._logger.debug(f"Sent Message: {data}")
            return True
            
        except ConnectionResetError:
            self._logger.warning("Connection lost, attempting to reconnect.")
            return await self._handle_reconnect_and_retry(data)
            
        except aiohttp.ClientError as e:
            self._logger.error(f"Client error sending message: {e}")
            return False
            
        except Exception as e:
            self._logger.error(f"Unexpected error sending message: {e}")
            return False

    async def _handle_reconnect_and_retry(self, data: dict, max_retries: int = 2) -> bool:
        """Handle reconnection and retry message sending."""
        for retry in range(max_retries):
            try:
                await self._attempt_reconnection()
                
                if self.is_connected:
                    await asyncio.sleep(0.5)  # Brief delay for connection stability
                    await self._websocket.send_json(data)
                    self._logger.debug(f"Sent message after reconnection (retry {retry + 1})")
                    return True
                    
            except Exception as e:
                self._logger.error(f"Retry {retry + 1} failed: {e}")
                
        self._logger.error("Failed to send message after reconnection attempts")
        return False
                    
    async def connect(self) -> 'IPCClient':
        """Enhanced connection method with better error handling."""
        if self._is_connecting:
            self._logger.debug("Connection already in progress, waiting...")
            # Wait for existing connection attempt
            while self._is_connecting:
                await asyncio.sleep(0.1)
            return self
            
        if self._is_connected:
            self._logger.debug("Already connected")
            return self
            
        self._is_connecting = True
        self._metrics.connect_attempts += 1
        
        try:
            # Create session if needed
            if not self._session or self._session.closed:
                self._session = await self._create_session()

            self._logger.info(f"Connecting to {self._websocket_url}")
            
            # Connect with enhanced error handling
            self._websocket = await self._session.ws_connect(
                self._websocket_url, 
                headers=self._headers, 
                heartbeat=self._heartbeat,
                autoping=True,
                compress=15  # Enable compression
            )

            # Start message listener
            self._task = asyncio.create_task(
                self._listen(), 
                name="ipc_message_listener"
            )
            
            self._is_connected = True
            self._metrics.last_connect_time = time.time()
            
            self._logger.info(f"Successfully connected to dashboard! (Attempt #{self._metrics.connect_attempts})")
        
        except aiohttp.ClientConnectorError as e:
            error_msg = f"Connection failed - unable to reach {self._host}:{self._port}"
            self._logger.error(error_msg)
            raise ConnectionError(error_msg) from e
            
        except aiohttp.WSServerHandshakeError as e:
            if e.status == 401:
                self._logger.error("Authentication failed: Invalid password or bot ID")
            elif e.status == 403:
                self._logger.error("Access forbidden: Check bot permissions or version compatibility")
            else:
                self._logger.error(f"WebSocket handshake failed: {e}")
            raise
            
        except Exception as e:
            self._logger.error(f"Unexpected error during connection: {e}", exc_info=True)
            raise
        
        finally:
            self._is_connecting = False
            
        return self

    async def disconnect(self) -> None:
        """Enhanced disconnect with proper resource cleanup."""
        self._logger.info("Initiating disconnect...")
        self._is_connected = False
        
        # Cancel message listener task
        if self._task and not self._task.cancelled():
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            self._task = None
        
        # Close WebSocket connection
        if self._websocket and not self._websocket.closed:
            try:
                await self._websocket.close()
            except Exception as e:
                self._logger.warning(f"Error closing WebSocket: {e}")
            self._websocket = None
        
        # Close HTTP session
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception as e:
                self._logger.warning(f"Error closing session: {e}")
            self._session = None
        
        # Close connector
        if self._connector and not self._connector.closed:
            try:
                await self._connector.close()
            except Exception as e:
                self._logger.warning(f"Error closing connector: {e}")
            self._connector = None
        
        self._logger.info("Disconnected from dashboard!")

    def get_metrics(self) -> Dict:
        """Get connection metrics for monitoring."""
        return {
            "connect_attempts": self._metrics.connect_attempts,
            "reconnect_count": self._metrics.reconnect_count,
            "message_count": self._metrics.message_count,
            "last_connect_time": self._metrics.last_connect_time,
            "last_heartbeat": self._metrics.last_heartbeat,
            "is_connected": self.is_connected,
            "uptime": time.time() - self._metrics.last_connect_time if self._metrics.last_connect_time else 0
        }

    @property
    def is_connected(self) -> bool:
        """Enhanced connection status check."""
        return (
            self._is_connected and 
            self._websocket and 
            not self._websocket.closed and
            self._session and
            not self._session.closed
        )

    def __repr__(self) -> str:
        return f"IPCClient(host={self._host}, port={self._port}, connected={self.is_connected})"