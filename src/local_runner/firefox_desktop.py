"""Selenium service whose browser never opens on the interactive desktop."""

from selenium.webdriver.firefox.service import Service

from .windows_desktop import DesktopProcess, PrivateDesktop


class PrivateDesktopFirefoxService(Service):
    def __init__(self, **kwargs):
        self.desktop = None
        self.process = None
        super().__init__(**kwargs)

    def _start_process(self, path):
        self.desktop = PrivateDesktop()
        try:
            self.process = DesktopProcess(
                [path, *self.command_line_args()], desktop=self.desktop, env=self.env,
                stdout=self.log_output if hasattr(self.log_output, "fileno") else None,
            )
        except BaseException:
            self.desktop.close()
            self.desktop = None
            raise

    def stop(self):
        try:
            super().stop()
        finally:
            if self.process is not None and self.process.poll() is not None:
                self.process.close()
                self.process = None
            if self.desktop is not None and self.process is None:
                self.desktop.close()
                self.desktop = None
