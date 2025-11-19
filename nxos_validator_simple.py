#!/usr/bin/env python3
"""
NX-OS Simple Validator

Script de validation pour Cisco Nexus (NX-OS)
- Collecte des données pré/post upgrade
- Compare les états et détecte les changements
- Génère des rapports détaillés

Author: Network Team
Version: 2.0
"""

import paramiko
import yaml
import os
import sys
import shutil
import re
from datetime import datetime
from getpass import getpass

# Directories for data storage
PRE_DIR = "pre_validation"
POST_DIR = "post_validation"
COMPARE_DIR = "comparison"

# NX-OS show commands to execute
COMMANDS = [
    "show version",
    "show interface status",
    "show ip bgp summary vrf all",
    "show ip ospf neighbors vrf all",
    "show cdp neighbors",
    "show lldp neighbors",
    "show ip route summary vrf all",
    "show ip route vrf all"
]

class NXOSValidator:
    """
    Validator for Cisco NX-OS devices

    Handles:
    - SSH connections to devices
    - Command execution with full output capture
    - Data parsing and comparison
    - Report generation
    """

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.devices = []

    def load_devices(self, yaml_file):
        """Load device list from YAML"""
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
            self.devices = data['devices']
        print(f"[INFO] Loaded {len(self.devices)} device(s)")
        for dev in self.devices:
            print(f"  - {dev['hostname']} ({dev['ip']})")

    def connect_device(self, device_ip, device_hostname):
        """Connect to device via SSH"""
        try:
            print(f"\n[{device_hostname}] Connecting to {device_ip}...")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=device_ip,
                username=self.username,
                password=self.password,
                timeout=30,
                look_for_keys=False,
                allow_agent=False
            )
            print(f"[{device_hostname}] Connected")
            return ssh
        except Exception as e:
            print(f"[{device_hostname}] ERROR: {str(e)}")
            return None

    def execute_command(self, ssh, command, timeout=60):
        """Execute command and get RAW output"""
        try:
            shell = ssh.invoke_shell(width=500, height=5000)
            shell.settimeout(timeout)

            import time
            time.sleep(1)

            # Clear initial buffer
            if shell.recv_ready():
                shell.recv(65535)

            # Disable paging
            shell.send('terminal length 0\n')
            time.sleep(0.5)
            if shell.recv_ready():
                shell.recv(65535)

            # Send command
            shell.send(command + '\n')
            time.sleep(2)

            # Collect ALL output
            output = ""
            max_wait = 30  # Maximum 30 seconds
            start_time = time.time()

            while (time.time() - start_time) < max_wait:
                if shell.recv_ready():
                    chunk = shell.recv(65535).decode('utf-8', errors='ignore')
                    output += chunk
                    time.sleep(0.1)
                else:
                    # Wait a bit more to make sure we got everything
                    time.sleep(0.5)
                    if shell.recv_ready():
                        chunk = shell.recv(65535).decode('utf-8', errors='ignore')
                        output += chunk
                    else:
                        break

            # Clean up - remove command echo and prompt
            lines = output.split('\n')
            clean_lines = []
            skip_first = True

            for line in lines:
                # Skip command echo line
                if skip_first and command in line:
                    skip_first = False
                    continue

                # Skip prompt lines (lines ending with #)
                line_stripped = line.strip()
                if line_stripped.endswith('#') and len(line_stripped) < 50:
                    continue

                clean_lines.append(line.rstrip('\r'))

            return '\n'.join(clean_lines)

        except Exception as e:
            return f"ERROR executing command: {str(e)}"

    def validate_hostname(self, ssh, expected_hostname):
        """Validate device hostname"""
        try:
            output = self.execute_command(ssh, "show hostname", timeout=10)
            actual_hostname_full = output.strip().split('\n')[-1].strip()
            actual_hostname = actual_hostname_full.split('.')[0]
            expected = expected_hostname.split('.')[0]

            if actual_hostname.lower() == expected.lower():
                print(f"[{expected_hostname}] Hostname validated: {actual_hostname_full}")
                return True
            else:
                print(f"[{expected_hostname}] ERROR: Hostname mismatch!")
                print(f"  Expected: {expected}")
                print(f"  Got: {actual_hostname}")
                return False
        except Exception as e:
            print(f"[{expected_hostname}] ERROR validating hostname: {str(e)}")
            return False

    def print_progress_bar(self, current, total, cmd, hostname, bar_length=40):
        """Print a dynamic progress bar"""
        percentage = int((current / total) * 100)
        filled_length = int(bar_length * current // total)
        bar = '=' * filled_length + '>' + ' ' * (bar_length - filled_length - 1)

        # Truncate command if too long
        cmd_display = cmd if len(cmd) <= 50 else cmd[:47] + "..."

        # Build the progress line
        progress_line = f'[{hostname}] [{bar}] {percentage:3d}% | {cmd_display}'

        # Pad with spaces to ensure we overwrite previous longer lines (120 chars total)
        progress_line = progress_line.ljust(120)

        # Print progress bar on same line
        print(f'\r{progress_line}', end='', flush=True)

    def collect_data(self, device, output_dir):
        """Collect RAW command outputs from device"""
        hostname = device['hostname']
        ip = device['ip']

        print(f"\n{'='*70}")
        print(f"Collecting data from {hostname} ({ip})")
        print(f"{'='*70}")

        # Connect
        ssh = self.connect_device(ip, hostname)
        if not ssh:
            return None

        # Validate hostname
        if not self.validate_hostname(ssh, hostname):
            print(f"[{hostname}] ABORTING - hostname mismatch")
            ssh.close()
            return None

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Output file with timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output_file = os.path.join(output_dir, f"{hostname}_{timestamp}.txt")

        total_commands = len(COMMANDS)

        with open(output_file, 'w') as f:
            # Header
            f.write("="*80 + "\n")
            f.write(f"DEVICE: {hostname} ({ip})\n")
            f.write(f"TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")

            # Execute each command and save RAW output
            for idx, cmd in enumerate(COMMANDS, 1):
                # Show progress bar
                self.print_progress_bar(idx - 1, total_commands, f"Starting: {cmd}", hostname)

                f.write("\n" + "="*80 + "\n")
                f.write(f"COMMAND: {cmd}\n")
                f.write("="*80 + "\n")

                output = self.execute_command(ssh, cmd)
                f.write(output)
                f.write("\n")

                # Update progress bar to show completion of this command
                self.print_progress_bar(idx, total_commands, f"Completed: {cmd}", hostname)

        # Print newline after progress bar completes
        print()

        ssh.close()
        print(f"[{hostname}] Disconnected")
        print(f"[{hostname}] Data saved to {output_file}")

        return output_file

    def get_latest_file(self, directory, hostname):
        """Get the most recent file for a given hostname"""
        if not os.path.exists(directory):
            return None

        # Find all files matching hostname pattern
        pattern = f"{hostname}_*.txt"
        files = [f for f in os.listdir(directory) if f.startswith(f"{hostname}_") and f.endswith('.txt')]

        if not files:
            # Try without timestamp (backward compatibility)
            old_pattern = f"{hostname}.txt"
            if os.path.exists(os.path.join(directory, old_pattern)):
                return os.path.join(directory, old_pattern)
            return None

        # Sort by filename (timestamp is in filename) and get the latest
        files.sort(reverse=True)
        return os.path.join(directory, files[0])

    def compare_data(self, pre_file, post_file, hostname):
        """Compare PRE and POST data"""
        print(f"\n{'='*70}")
        print(f"COMPARING: {hostname}")
        print(f"{'='*70}")

        # Read files
        with open(pre_file, 'r') as f:
            pre_content = f.read()
        with open(post_file, 'r') as f:
            post_content = f.read()

        # Parse data from both files
        pre_data = self.parse_data(pre_content)
        post_data = self.parse_data(post_content)

        # Create comparison report
        os.makedirs(COMPARE_DIR, exist_ok=True)
        report_file = os.path.join(COMPARE_DIR, f"{hostname}_report.txt")

        issues = []

        with open(report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write(f"COMPARISON REPORT: {hostname}\n")
            f.write("="*80 + "\n")
            f.write(f"PRE:  {pre_data['timestamp']}\n")
            f.write(f"POST: {post_data['timestamp']}\n")
            f.write("="*80 + "\n\n")

            # Version
            f.write("VERSION:\n")
            f.write("-"*80 + "\n")
            pre_ver = pre_data.get('version', 'Unknown')
            post_ver = post_data.get('version', 'Unknown')
            if pre_ver != post_ver:
                f.write(f"  CHANGED: {pre_ver} -> {post_ver}\n")
            else:
                f.write(f"  UNCHANGED: {pre_ver}\n")
                if pre_ver != 'Unknown':
                    issues.append(f"Version NOT changed - still {pre_ver}")
            f.write("\n")

            # Interfaces
            f.write("INTERFACES:\n")
            f.write("-"*80 + "\n")
            intf_issues = self.compare_interfaces(pre_data, post_data, f)
            issues.extend(intf_issues)
            f.write("\n")

            # BGP
            f.write("BGP NEIGHBORS:\n")
            f.write("-"*80 + "\n")
            bgp_issues = self.compare_bgp(pre_data, post_data, f)
            issues.extend(bgp_issues)
            f.write("\n")

            # OSPF
            f.write("OSPF NEIGHBORS:\n")
            f.write("-"*80 + "\n")
            ospf_issues = self.compare_ospf(pre_data, post_data, f)
            issues.extend(ospf_issues)
            f.write("\n")

            # CDP
            f.write("CDP NEIGHBORS:\n")
            f.write("-"*80 + "\n")
            cdp_issues = self.compare_cdp_lldp(pre_data.get('cdp', []), post_data.get('cdp', []), f, "CDP")
            issues.extend(cdp_issues)
            f.write("\n")

            # LLDP
            f.write("LLDP NEIGHBORS:\n")
            f.write("-"*80 + "\n")
            lldp_issues = self.compare_cdp_lldp(pre_data.get('lldp', []), post_data.get('lldp', []), f, "LLDP")
            issues.extend(lldp_issues)
            f.write("\n")

            # Route Summary
            f.write("ROUTE SUMMARY:\n")
            f.write("-"*80 + "\n")
            route_summary_issues = self.compare_route_summary(pre_data, post_data, f)
            issues.extend(route_summary_issues)
            f.write("\n")

            # Routes
            f.write("ROUTES:\n")
            f.write("-"*80 + "\n")
            route_issues = self.compare_routes(pre_data, post_data, f)
            issues.extend(route_issues)
            f.write("\n")

            # Summary
            f.write("="*80 + "\n")
            f.write("SUMMARY\n")
            f.write("="*80 + "\n")
            if issues:
                f.write(f"\nISSUES FOUND ({len(issues)}):\n")
                for issue in issues:
                    f.write(f"  ! {issue}\n")
            else:
                f.write("\nNO CRITICAL ISSUES\n")

        print(f"[{hostname}] Report saved to {report_file}")

    def parse_data(self, content):
        """Parse data from saved file"""
        data = {
            'timestamp': '',
            'version': '',
            'interfaces': {},
            'bgp': {},
            'ospf': {},
            'cdp': [],
            'lldp': [],
            'routes': {},
            'route_summary': {}
        }

        lines = content.split('\n')
        current_command = None
        command_output = []

        for line in lines:
            if line.startswith('TIMESTAMP:'):
                data['timestamp'] = line.split(':', 1)[1].strip()

            if line.startswith('COMMAND:'):
                # Save previous command output
                if current_command and command_output:
                    output_text = '\n'.join(command_output)
                    self.parse_command_output(current_command, output_text, data)

                current_command = line.split(':', 1)[1].strip()
                command_output = []
            elif current_command:
                if not line.startswith('==='):
                    command_output.append(line)

        # Parse last command
        if current_command and command_output:
            output_text = '\n'.join(command_output)
            self.parse_command_output(current_command, output_text, data)

        return data

    def parse_command_output(self, command, output, data):
        """Parse specific command output"""
        if 'show version' in command:
            # Extract version
            for line in output.split('\n'):
                if 'NXOS' in line.upper():
                    match = re.search(r'version\s+([\d\.]+\(\d+\))', line, re.IGNORECASE)
                    if match:
                        data['version'] = match.group(1)
                        break

        elif 'show interface status' in command:
            # Parse interfaces - capture status and vlan
            # Format: Port Name Status Vlan Duplex Speed Type
            for line in output.split('\n'):
                parts = line.split()
                if len(parts) >= 3 and (parts[0].startswith('Eth') or parts[0].startswith('Vlan') or parts[0].startswith('Lo') or parts[0].startswith('mgmt')):
                    data['interfaces'][parts[0]] = {
                        'vlan': parts[3] if len(parts) > 3 else '--',  # Fixed: VLAN is at index 3
                        'status': parts[2] if len(parts) > 2 else 'unknown'
                    }

        elif 'show ip bgp summary vrf all' in command:
            # Parse BGP
            current_vrf = None
            for line in output.split('\n'):
                if 'VRF' in line and 'address family' in line:
                    match = re.search(r'VRF\s+(\S+)', line)
                    if match:
                        current_vrf = match.group(1).strip(',')
                        data['bgp'][current_vrf] = []
                elif current_vrf and re.match(r'^\d+\.\d+\.\d+\.\d+', line.strip()):
                    parts = line.split()
                    if len(parts) >= 1:
                        data['bgp'][current_vrf].append({
                            'neighbor': parts[0],
                            'state': parts[-1]
                        })

        elif 'show ip ospf neighbors vrf all' in command:
            # Parse OSPF
            current_vrf = None
            for line in output.split('\n'):
                if 'OSPF Process ID' in line and 'VRF' in line:
                    match = re.search(r'VRF\s+(\S+)', line)
                    if match:
                        current_vrf = match.group(1)
                        data['ospf'][current_vrf] = []
                elif current_vrf and re.match(r'^\s*\d+\.\d+\.\d+\.\d+', line):
                    parts = line.split()
                    if len(parts) >= 3:
                        data['ospf'][current_vrf].append({
                            'neighbor': parts[0],
                            'state': parts[2]
                        })

        elif 'show cdp neighbors' in command:
            # Parse CDP
            for line in output.split('\n'):
                if 'Eth' in line or 'mgmt' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        for i, p in enumerate(parts):
                            if 'Eth' in p or 'mgmt' in p or 'Gig' in p:
                                data['cdp'].append(parts[0] + '|' + p)
                                break

        elif 'show lldp neighbors' in command:
            # Parse LLDP
            for line in output.split('\n'):
                if 'Eth' in line or 'mgmt' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        for i, p in enumerate(parts):
                            if 'Eth' in p or 'mgmt' in p or 'Gig' in p:
                                data['lldp'].append(parts[0] + '|' + p)
                                break

        elif 'show ip route summary vrf all' in command:
            # Parse route summary - only bgp, ospf, static, direct, local
            current_vrf = None
            for line in output.split('\n'):
                if 'IP Route Table for VRF' in line:
                    match = re.search(r'VRF\s+"?(\S+)"?', line)
                    if match:
                        current_vrf = match.group(1).strip('"')
                        data['route_summary'][current_vrf] = {}
                elif current_vrf and ':' in line:
                    line_stripped = line.strip()
                    if (line_stripped.startswith('bgp-') or line_stripped.startswith('ospf-') or
                        line_stripped.startswith('static') or line_stripped.startswith('direct') or
                        line_stripped.startswith('local')):
                        # Parse lines like "  bgp-65000      : 20" or "  local          : 12"
                        parts = line.split(':')
                        if len(parts) == 2:
                            protocol = parts[0].strip()
                            count = parts[1].strip().split()[0]  # Get first value (ignore "None")

                            # Normalize protocol names: bgp-65000 -> bgp, ospf-10 -> ospf
                            if protocol.startswith('bgp-'):
                                protocol = 'bgp'
                            elif protocol.startswith('ospf-'):
                                protocol = 'ospf'

                            try:
                                data['route_summary'][current_vrf][protocol] = int(count)
                            except ValueError:
                                pass

        elif 'show ip route vrf all' in command and 'summary' not in command:
            # Parse routes
            current_vrf = None
            for line in output.split('\n'):
                if 'IP Route Table for VRF' in line:
                    match = re.search(r'VRF\s+"?(\S+)"?', line)
                    if match:
                        current_vrf = match.group(1).strip('"')
                        if current_vrf not in data['routes']:
                            data['routes'][current_vrf] = []
                elif current_vrf:
                    # Look for routes
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+/\d+)', line)
                    if match:
                        data['routes'][current_vrf].append(match.group(1))

    def compare_interfaces(self, pre, post, f):
        """Compare interfaces - status and VLAN with ALL state changes"""
        issues = []
        pre_intf = pre.get('interfaces', {})
        post_intf = post.get('interfaces', {})

        down_intfs = []
        up_intfs = []
        status_changed = []
        vlan_changed = []
        removed_intfs = []
        added_intfs = []

        # Check interfaces from PRE
        for intf, pre_data in pre_intf.items():
            post_data = post_intf.get(intf)

            if not post_data:
                removed_intfs.append(intf)
                issues.append(f"Interface REMOVED: {intf}")
                continue

            # Handle old format (string) vs new format (dict)
            if isinstance(pre_data, str):
                pre_status = pre_data
                pre_vlan = '--'
            else:
                pre_status = pre_data.get('status', 'unknown')
                pre_vlan = pre_data.get('vlan', '--')

            if isinstance(post_data, str):
                post_status = post_data
                post_vlan = '--'
            else:
                post_status = post_data.get('status', 'unknown')
                post_vlan = post_data.get('vlan', '--')

            # Check for ANY status change
            if pre_status != post_status:
                # Went DOWN (connected → not connected)
                if 'connected' in pre_status.lower() and 'connected' not in post_status.lower():
                    down_intfs.append(f"{intf}: {pre_status} -> {post_status}")
                    issues.append(f"Interface DOWN: {intf}")
                # Came UP (not connected → connected)
                elif 'connected' not in pre_status.lower() and 'connected' in post_status.lower():
                    up_intfs.append(f"{intf}: {pre_status} -> {post_status}")
                    # Note: UP is good news, not an issue
                # Other status change
                else:
                    status_changed.append(f"{intf}: {pre_status} -> {post_status}")

            # Check if VLAN changed
            if pre_vlan != post_vlan:
                vlan_changed.append(f"{intf}: VLAN {pre_vlan} -> {post_vlan}")
                issues.append(f"Interface VLAN changed: {intf} ({pre_vlan} -> {post_vlan})")

        # Check for ADDED interfaces (in POST but not in PRE)
        for intf in post_intf:
            if intf not in pre_intf:
                added_intfs.append(intf)
                issues.append(f"Interface ADDED: {intf}")

        # Write results
        if removed_intfs:
            f.write(f"  INTERFACES REMOVED ({len(removed_intfs)}):\n")
            for intf in removed_intfs:
                f.write(f"    ! {intf}\n")

        if added_intfs:
            f.write(f"  INTERFACES ADDED ({len(added_intfs)}):\n")
            for intf in added_intfs:
                f.write(f"    + {intf}\n")

        if down_intfs:
            f.write(f"  INTERFACES WENT DOWN ({len(down_intfs)}):\n")
            for intf in down_intfs:
                f.write(f"    ! {intf}\n")

        if up_intfs:
            f.write(f"  INTERFACES CAME UP ({len(up_intfs)}):\n")
            for intf in up_intfs:
                f.write(f"    + {intf}\n")

        if status_changed:
            f.write(f"  INTERFACE STATUS CHANGED ({len(status_changed)}):\n")
            for intf in status_changed:
                f.write(f"    ~ {intf}\n")

        if vlan_changed:
            f.write(f"  INTERFACE VLAN CHANGED ({len(vlan_changed)}):\n")
            for intf in vlan_changed:
                f.write(f"    ~ {intf}\n")

        if not (removed_intfs or added_intfs or down_intfs or up_intfs or status_changed or vlan_changed):
            f.write("  OK: No interface changes\n")

        return issues

    def compare_bgp(self, pre, post, f):
        """Compare BGP with state change detection"""
        issues = []
        pre_bgp = pre.get('bgp', {})
        post_bgp = post.get('bgp', {})

        for vrf in sorted(set(list(pre_bgp.keys()) + list(post_bgp.keys()))):
            pre_neighbors = {n['neighbor']: n['state'] for n in pre_bgp.get(vrf, [])}
            post_neighbors = {n['neighbor']: n['state'] for n in post_bgp.get(vrf, [])}

            vrf_has_issues = False

            # Check for MISSING neighbors
            missing = [n for n in pre_neighbors if n not in post_neighbors]
            if missing:
                f.write(f"  VRF {vrf} - MISSING ({len(missing)}):\n")
                for n in missing:
                    f.write(f"    ! {n}\n")
                    issues.append(f"BGP neighbor MISSING in VRF {vrf}: {n}")
                vrf_has_issues = True

            # Check for NEW neighbors
            new = [n for n in post_neighbors if n not in pre_neighbors]
            if new:
                f.write(f"  VRF {vrf} - NEW ({len(new)}):\n")
                for n in new:
                    f.write(f"    + {n} (state: {post_neighbors[n]})\n")
                # New neighbors are not issues (good news)

            # Check for state changes
            state_changes = []
            down_neighbors = []

            for n in pre_neighbors:
                if n in post_neighbors:
                    pre_state = pre_neighbors[n]
                    post_state = post_neighbors[n]

                    # State changed?
                    if pre_state != post_state:
                        # Check if it's a number (Established = shows prefix count)
                        pre_is_up = pre_state.isdigit()
                        post_is_up = post_state.isdigit()

                        if pre_is_up and not post_is_up:
                            # Went DOWN (number → Idle/Active/etc)
                            state_changes.append(f"    ! {n}: Established ({pre_state} pfx) -> {post_state}")
                            issues.append(f"BGP neighbor DOWN in VRF {vrf}: {n} (was Established, now {post_state})")
                            vrf_has_issues = True
                        elif not pre_is_up and post_is_up:
                            # Came UP (Idle/Active → number)
                            state_changes.append(f"    + {n}: {pre_state} -> Established ({post_state} pfx)")
                            # UP is good news, not an issue
                        else:
                            # Other state change (Idle → Active, etc.)
                            state_changes.append(f"    ~ {n}: {pre_state} -> {post_state}")

                    # Check if currently DOWN (even if no change)
                    elif post_state in ['Idle', 'Active', 'Connect']:
                        down_neighbors.append(f"    ! {n} ({post_state})")
                        issues.append(f"BGP neighbor DOWN in VRF {vrf}: {n}")
                        vrf_has_issues = True

            if state_changes:
                f.write(f"  VRF {vrf} - STATE CHANGES ({len(state_changes)}):\n")
                for change in state_changes:
                    f.write(change + "\n")
                vrf_has_issues = True

            if down_neighbors and not state_changes:
                # Show DOWN neighbors that didn't change state
                f.write(f"  VRF {vrf} - DOWN ({len(down_neighbors)}):\n")
                for n in down_neighbors:
                    f.write(n + "\n")

        if not issues:
            f.write("  OK: No BGP issues\n")

        return issues

    def compare_ospf(self, pre, post, f):
        """Compare OSPF with state change detection"""
        issues = []
        pre_ospf = pre.get('ospf', {})
        post_ospf = post.get('ospf', {})

        for vrf in sorted(set(list(pre_ospf.keys()) + list(post_ospf.keys()))):
            pre_neighbors = {n['neighbor']: n['state'] for n in pre_ospf.get(vrf, [])}
            post_neighbors = {n['neighbor']: n['state'] for n in post_ospf.get(vrf, [])}

            vrf_has_issues = False

            # Check for MISSING neighbors
            missing = [n for n in pre_neighbors if n not in post_neighbors]
            if missing:
                f.write(f"  VRF {vrf} - MISSING ({len(missing)}):\n")
                for n in missing:
                    f.write(f"    ! {n}\n")
                    issues.append(f"OSPF neighbor MISSING in VRF {vrf}: {n}")
                vrf_has_issues = True

            # Check for NEW neighbors
            new = [n for n in post_neighbors if n not in pre_neighbors]
            if new:
                f.write(f"  VRF {vrf} - NEW ({len(new)}):\n")
                for n in new:
                    f.write(f"    + {n} (state: {post_neighbors[n]})\n")
                # New neighbors are not issues

            # Check for state changes
            state_changes = []
            not_full = []

            for n in pre_neighbors:
                if n in post_neighbors:
                    pre_state = pre_neighbors[n]
                    post_state = post_neighbors[n]

                    # State changed?
                    if pre_state != post_state:
                        if 'FULL' in pre_state and 'FULL' not in post_state:
                            # Went DOWN (FULL → other)
                            state_changes.append(f"    ! {n}: {pre_state} -> {post_state}")
                            issues.append(f"OSPF neighbor went DOWN in VRF {vrf}: {n} ({pre_state} -> {post_state})")
                            vrf_has_issues = True
                        elif 'FULL' not in pre_state and 'FULL' in post_state:
                            # Came UP (other → FULL)
                            state_changes.append(f"    + {n}: {pre_state} -> {post_state}")
                            # UP is good news
                        else:
                            # Other state change
                            state_changes.append(f"    ~ {n}: {pre_state} -> {post_state}")

                    # Check if currently NOT FULL (even if no change)
                    elif 'FULL' not in post_state:
                        not_full.append(f"    ! {n} ({post_state})")
                        issues.append(f"OSPF neighbor NOT FULL in VRF {vrf}: {n}")
                        vrf_has_issues = True

            if state_changes:
                f.write(f"  VRF {vrf} - STATE CHANGES ({len(state_changes)}):\n")
                for change in state_changes:
                    f.write(change + "\n")
                vrf_has_issues = True

            if not_full and not state_changes:
                # Show NOT FULL neighbors that didn't change state
                f.write(f"  VRF {vrf} - NOT FULL ({len(not_full)}):\n")
                for n in not_full:
                    f.write(n + "\n")

        if not issues:
            f.write("  OK: No OSPF issues\n")

        return issues

    def compare_cdp_lldp(self, pre, post, f, protocol):
        """Compare CDP/LLDP with new neighbor detection"""
        issues = []
        pre_set = set(pre)
        post_set = set(post)

        missing = pre_set - post_set
        new = post_set - pre_set

        if missing:
            f.write(f"  MISSING {protocol} neighbors ({len(missing)}):\n")
            for m in sorted(missing):
                f.write(f"    ! {m}\n")
                issues.append(f"{protocol} neighbor MISSING: {m}")

        if new:
            f.write(f"  NEW {protocol} neighbors ({len(new)}):\n")
            for n in sorted(new):
                f.write(f"    + {n}\n")
            # New neighbors are not issues

        if not missing and not new:
            f.write(f"  OK: No {protocol} neighbor changes\n")

        return issues

    def compare_route_summary(self, pre, post, f):
        """Compare route summary - only bgp, ospf, static, direct, local per VRF"""
        issues = []
        pre_summary = pre.get('route_summary', {})
        post_summary = post.get('route_summary', {})

        # Get all VRFs from both PRE and POST
        all_vrfs = sorted(set(list(pre_summary.keys()) + list(post_summary.keys())))

        # Protocols to track
        protocols = ['bgp', 'ospf', 'static', 'direct', 'local']

        for vrf in all_vrfs:
            pre_vrf = pre_summary.get(vrf, {})
            post_vrf = post_summary.get(vrf, {})

            f.write(f"\n  VRF {vrf}:\n")

            vrf_has_changes = False
            for protocol in protocols:
                pre_count = pre_vrf.get(protocol, 0)
                post_count = post_vrf.get(protocol, 0)

                if pre_count != post_count:
                    vrf_has_changes = True
                    diff = post_count - pre_count
                    diff_str = f"+{diff}" if diff > 0 else str(diff)
                    f.write(f"    {protocol:8}: {pre_count:4} -> {post_count:4} ({diff_str})\n")
                    issues.append(f"Route count changed in VRF {vrf}: {protocol} ({pre_count} -> {post_count})")
                else:
                    # Show unchanged counts
                    f.write(f"    {protocol:8}: {pre_count:4} (unchanged)\n")

            if not vrf_has_changes:
                # No issues for this VRF
                pass

        if not issues:
            # All good - can add summary message if needed
            pass

        return issues

    def compare_routes(self, pre, post, f):
        """Compare routes and identify added/removed routes"""
        pre_routes = pre.get('routes', {})
        post_routes = post.get('routes', {})
        issues = []

        for vrf in sorted(set(list(pre_routes.keys()) + list(post_routes.keys()))):
            pre_route_list = pre_routes.get(vrf, [])
            post_route_list = post_routes.get(vrf, [])

            # Convert to sets for comparison
            pre_set = set(pre_route_list)
            post_set = set(post_route_list)

            # Find missing and added routes
            missing_routes = pre_set - post_set
            added_routes = post_set - pre_set

            pre_count = len(pre_route_list)
            post_count = len(post_route_list)

            # Display VRF header
            f.write(f"\n  VRF {vrf}:\n")
            f.write(f"    Total routes: {pre_count} -> {post_count}\n")

            # Display missing routes - SHOW ALL!
            if missing_routes:
                f.write(f"    ROUTES REMOVED ({len(missing_routes)}):\n")
                for route in sorted(missing_routes):
                    f.write(f"      - {route}\n")

                # Add to issues
                issues.append(f"Routes REMOVED in VRF {vrf}: {len(missing_routes)} route(s)")

            # Display added routes - SHOW ALL!
            if added_routes:
                f.write(f"    ROUTES ADDED ({len(added_routes)}):\n")
                for route in sorted(added_routes):
                    f.write(f"      + {route}\n")

            # If no changes
            if not missing_routes and not added_routes:
                f.write(f"    OK: No route changes\n")

        return issues


def main():
    print("\n" + "="*80)
    print("NX-OS SIMPLE VALIDATOR")
    print("="*80)

    print("\nSelect mode:")
    print("  1 - PRE-UPGRADE: Collect baseline (keeps history with timestamp)")
    print("  2 - POST-UPGRADE: Collect data (keeps history with timestamp)")
    print("  3 - COMPARE ONLY: Compare files (auto or manual selection)")

    mode = input("\nEnter choice (1, 2, or 3): ").strip()

    if mode not in ['1', '2', '3']:
        print("Invalid choice")
        sys.exit(1)

    is_pre = (mode == '1')
    is_compare_only = (mode == '3')

    # For compare-only mode, we don't need SSH credentials
    if is_compare_only:
        validator = NXOSValidator('', '')
        validator.load_devices('ip-device.yml')

        print("\n[MODE] COMPARE ONLY")

        # Check if PRE and POST directories exist
        if not os.path.exists(PRE_DIR):
            print(f"\nERROR: {PRE_DIR}/ directory not found")
            print("Please run PRE-UPGRADE mode first")
            sys.exit(1)

        if not os.path.exists(POST_DIR):
            print(f"\nERROR: {POST_DIR}/ directory not found")
            print("Please run POST-UPGRADE mode first")
            sys.exit(1)

        # Remove old comparison directory
        if os.path.exists(COMPARE_DIR):
            shutil.rmtree(COMPARE_DIR)

        print(f"\n{'='*80}")
        print("COMPARE MODE")
        print(f"{'='*80}")

        # Ask user if they want to compare all or select specific files
        print("\nOptions:")
        print("  1 - Compare ALL devices (latest files)")
        print("  2 - Select specific files to compare")
        compare_choice = input("\nYour choice (1/2): ").strip()

        files_to_compare = []

        if compare_choice == '2':
            # MANUAL FILE SELECTION MODE
            print(f"\n{'='*80}")
            print("FILE SELECTION MODE")
            print(f"{'='*80}")

            # List all PRE files
            print("\n--- Available PRE-VALIDATION files ---")
            if not os.path.exists(PRE_DIR):
                print("ERROR: PRE directory does not exist!")
                sys.exit(1)

            pre_files = [f for f in os.listdir(PRE_DIR) if f.endswith('.txt')]
            pre_files.sort(reverse=True)  # Most recent first

            if not pre_files:
                print("ERROR: No PRE files found!")
                sys.exit(1)

            for idx, filename in enumerate(pre_files, 1):
                file_path = os.path.join(PRE_DIR, filename)
                # Get file modification time
                mtime = os.path.getmtime(file_path)
                timestamp = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                print(f"  {idx}. {filename} (modified: {timestamp})")

            pre_selection = input(f"\nSelect PRE file (1-{len(pre_files)}): ").strip()
            try:
                pre_idx = int(pre_selection) - 1
                if pre_idx < 0 or pre_idx >= len(pre_files):
                    print("Invalid selection!")
                    sys.exit(1)
                selected_pre_file = os.path.join(PRE_DIR, pre_files[pre_idx])
            except ValueError:
                print("Invalid input!")
                sys.exit(1)

            # List all POST files
            print("\n--- Available POST-VALIDATION files ---")
            if not os.path.exists(POST_DIR):
                print("ERROR: POST directory does not exist!")
                sys.exit(1)

            post_files = [f for f in os.listdir(POST_DIR) if f.endswith('.txt')]
            post_files.sort(reverse=True)  # Most recent first

            if not post_files:
                print("ERROR: No POST files found!")
                sys.exit(1)

            for idx, filename in enumerate(post_files, 1):
                file_path = os.path.join(POST_DIR, filename)
                # Get file modification time
                mtime = os.path.getmtime(file_path)
                timestamp = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                print(f"  {idx}. {filename} (modified: {timestamp})")

            post_selection = input(f"\nSelect POST file (1-{len(post_files)}): ").strip()
            try:
                post_idx = int(post_selection) - 1
                if post_idx < 0 or post_idx >= len(post_files):
                    print("Invalid selection!")
                    sys.exit(1)
                selected_post_file = os.path.join(POST_DIR, post_files[post_idx])
            except ValueError:
                print("Invalid input!")
                sys.exit(1)

            # Extract hostname from filename (hostname is before first underscore or .txt)
            pre_basename = os.path.basename(selected_pre_file)
            if '_' in pre_basename:
                hostname = pre_basename.split('_')[0]
            else:
                hostname = pre_basename.replace('.txt', '')

            files_to_compare.append({
                'pre': selected_pre_file,
                'post': selected_post_file,
                'hostname': hostname
            })

            print(f"\n{'='*80}")
            print(f"Will compare:")
            print(f"  PRE:  {os.path.basename(selected_pre_file)}")
            print(f"  POST: {os.path.basename(selected_post_file)}")
            print(f"{'='*80}")

        else:
            # AUTO MODE - Compare all devices using latest files
            print(f"\n{'='*80}")
            print("AUTO MODE - Comparing all devices (latest files)")
            print(f"{'='*80}")

            for device in validator.devices:
                hostname = device['hostname']

                # Get the most recent PRE and POST files
                pre_file = validator.get_latest_file(PRE_DIR, hostname)
                post_file = validator.get_latest_file(POST_DIR, hostname)

                if not pre_file:
                    print(f"\n[{hostname}] WARNING: No PRE data found")
                    continue

                if not post_file:
                    print(f"\n[{hostname}] WARNING: No POST data found")
                    continue

                files_to_compare.append({
                    'pre': pre_file,
                    'post': post_file,
                    'hostname': hostname
                })

        # Perform comparisons
        print(f"\n{'='*80}")
        print("Starting comparison...")
        print(f"{'='*80}")

        for item in files_to_compare:
            validator.compare_data(item['pre'], item['post'], item['hostname'])

        # Display all comparison reports on screen
        print(f"\n{'='*80}")
        print("COMPARISON REPORTS")
        print(f"{'='*80}\n")

        for item in files_to_compare:
            hostname = item['hostname']
            report_file = os.path.join(COMPARE_DIR, f"{hostname}_report.txt")

            if os.path.exists(report_file):
                with open(report_file, 'r') as f:
                    report_content = f.read()
                print(report_content)
                print("\n")

        print(f"{'='*80}")
        print(f"COMPARE ONLY completed!")
        print(f"Reports: {COMPARE_DIR}/")
        print(f"{'='*80}")

        sys.exit(0)

    # For PRE and POST modes, we need SSH credentials
    username = input("Enter SSH username: ").strip()
    password = getpass("Enter SSH password: ")

    validator = NXOSValidator(username, password)
    validator.load_devices('ip-device.yml')

    if is_pre:
        print("\n[MODE] PRE-UPGRADE")
        # Create directory if it doesn't exist (no longer deleting old data)
        os.makedirs(PRE_DIR, exist_ok=True)

        for device in validator.devices:
            validator.collect_data(device, PRE_DIR)

        print(f"\n{'='*80}")
        print(f"PRE-UPGRADE completed! Data saved in: {PRE_DIR}/")
        print(f"{'='*80}")

    else:
        print("\n[MODE] POST-UPGRADE")
        # Create directory if it doesn't exist (no longer deleting old data)
        os.makedirs(POST_DIR, exist_ok=True)

        for device in validator.devices:
            validator.collect_data(device, POST_DIR)

        print(f"\n{'='*80}")
        print(f"POST-UPGRADE data collection completed!")
        print(f"Data: {POST_DIR}/")
        print(f"\nTo compare PRE vs POST data, run option 3 (COMPARE ONLY)")
        print(f"{'='*80}")


if __name__ == "__main__":
    main()
