from __future__ import annotations

import shlex
import subprocess
from typing import Any

from app.containerization.models import DockerExecutionResult


class DockerClient:
    def __init__(self, docker_binary: str = "docker") -> None:
        self.docker_binary = docker_binary

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                [self.docker_binary, "info"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except OSError:
            return False

    def build_image(self, dockerfile_path: str, image_tag: str, build_context: str | None = None) -> DockerExecutionResult:
        context = build_context or "."
        command = [self.docker_binary, "build", "-f", dockerfile_path, "-t", image_tag, context]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            return DockerExecutionResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=result.returncode == 0,
                error=None if result.returncode == 0 else result.stderr or result.stdout,
                image_tag=image_tag,
            )
        except OSError as exc:
            return DockerExecutionResult(
                command=command,
                exit_code=None,
                stdout="",
                stderr="",
                success=False,
                error=str(exc),
                image_tag=image_tag,
            )

    def run_container(
        self,
        image_tag: str,
        command: list[str] | None = None,
        port: int | str | None = None,
        env: dict[str, str] | None = None,
        detach: bool = True,
    ) -> DockerExecutionResult:
        docker_command = [self.docker_binary, "run"]
        if detach:
            docker_command.append("-d")
        if port is not None:
            docker_command.extend(["-p", f"{port}:{port}"])
        if env:
            for key, value in env.items():
                docker_command.extend(["-e", f"{key}={value}"])
        docker_command.append(image_tag)
        if command:
            docker_command.extend(command)

        try:
            result = subprocess.run(docker_command, capture_output=True, text=True, check=False)
            container_id = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else None
            return DockerExecutionResult(
                command=docker_command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=result.returncode == 0,
                error=None if result.returncode == 0 else result.stderr or result.stdout,
                image_tag=image_tag,
                container_id=container_id,
            )
        except OSError as exc:
            return DockerExecutionResult(
                command=docker_command,
                exit_code=None,
                stdout="",
                stderr="",
                success=False,
                error=str(exc),
                image_tag=image_tag,
            )

    def inspect_container(self, container_id: str) -> DockerExecutionResult:
        command = [self.docker_binary, "inspect", container_id]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            return DockerExecutionResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=result.returncode == 0,
                error=None if result.returncode == 0 else result.stderr or result.stdout,
                container_id=container_id,
            )
        except OSError as exc:
            return DockerExecutionResult(
                command=command,
                exit_code=None,
                stdout="",
                stderr="",
                success=False,
                error=str(exc),
                container_id=container_id,
            )

    def logs(self, container_id: str, tail: int = 200) -> DockerExecutionResult:
        command = [self.docker_binary, "logs", "--tail", str(tail), container_id]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            return DockerExecutionResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=result.returncode == 0,
                error=None if result.returncode == 0 else result.stderr or result.stdout,
                container_id=container_id,
            )
        except OSError as exc:
            return DockerExecutionResult(
                command=command,
                exit_code=None,
                stdout="",
                stderr="",
                success=False,
                error=str(exc),
                container_id=container_id,
            )

    def stop_container(self, container_id: str) -> DockerExecutionResult:
        command = [self.docker_binary, "stop", container_id]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            return DockerExecutionResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=result.returncode == 0,
                error=None if result.returncode == 0 else result.stderr or result.stdout,
                container_id=container_id,
            )
        except OSError as exc:
            return DockerExecutionResult(
                command=command,
                exit_code=None,
                stdout="",
                stderr="",
                success=False,
                error=str(exc),
                container_id=container_id,
            )

    def remove_container(self, container_id: str, force: bool = True) -> DockerExecutionResult:
        command = [self.docker_binary, "rm", "-f", container_id] if force else [self.docker_binary, "rm", container_id]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            return DockerExecutionResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=result.returncode == 0,
                error=None if result.returncode == 0 else result.stderr or result.stdout,
                container_id=container_id,
            )
        except OSError as exc:
            return DockerExecutionResult(
                command=command,
                exit_code=None,
                stdout="",
                stderr="",
                success=False,
                error=str(exc),
                container_id=container_id,
            )

    def remove_image(self, image_tag: str, force: bool = True) -> DockerExecutionResult:
        command = [self.docker_binary, "rmi", "-f", image_tag] if force else [self.docker_binary, "rmi", image_tag]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            return DockerExecutionResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=result.returncode == 0,
                error=None if result.returncode == 0 else result.stderr or result.stdout,
                image_tag=image_tag,
            )
        except OSError as exc:
            return DockerExecutionResult(
                command=command,
                exit_code=None,
                stdout="",
                stderr="",
                success=False,
                error=str(exc),
                image_tag=image_tag,
            )

    @staticmethod
    def command_tokens(command: str) -> list[str]:
        return shlex.split(command)


__all__ = ["DockerClient", "DockerExecutionResult"]
