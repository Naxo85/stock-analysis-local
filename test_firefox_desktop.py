import ctypes
import subprocess
import sys
import json
from unittest.mock import Mock, patch

import pytest

from src.local_runner import chatgpt_browser_generator as browser
from src.local_runner import firefox_desktop
from src.local_runner import windows_desktop
from src.local_runner import ibkr_gateway_manager as gateway


@pytest.fixture(autouse=True)
def enable_private_desktop(monkeypatch):
    monkeypatch.setenv("ANALYSIS_PRIVATE_DESKTOP", "1")


def test_background_launch_assigns_private_desktop_before_starting_firefox(tmp_path):
    driver = Mock()
    with patch("selenium.webdriver.Firefox", return_value=driver) as launch, patch.object(
        firefox_desktop, "PrivateDesktopFirefoxService"
    ) as service, patch.object(browser, "_firefox_executable", return_value="firefox.exe"):
        assert browser._launch_firefox(tmp_path, headed=False) is driver
    assert launch.call_args.kwargs["service"] is service.return_value
    assert "-headless" not in launch.call_args.kwargs["options"].arguments
    prefs = launch.call_args.kwargs["options"].preferences
    assert prefs["layers.acceleration.disabled"] is True
    assert prefs["layers.gpu-process.enabled"] is False
    assert prefs["gfx.webrender.software"] is True
    assert prefs["gfx.webrender.software.d3d11"] is False
    driver.minimize_window.assert_not_called()


def test_interactive_login_stays_on_users_desktop(tmp_path):
    with patch("selenium.webdriver.Firefox") as launch, patch.object(
        firefox_desktop, "PrivateDesktopFirefoxService"
    ) as service, patch.object(browser, "_firefox_executable", return_value="firefox.exe"):
        browser._launch_firefox(tmp_path, headed=True)
    service.assert_not_called()
    assert "service" not in launch.call_args.kwargs
    assert "gfx.webrender.software" not in launch.call_args.kwargs["options"].preferences


def test_private_desktop_software_rendering_can_be_disabled_for_diagnosis(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALYSIS_FIREFOX_SOFTWARE_RENDERING", "0")
    with patch("selenium.webdriver.Firefox") as launch, patch.object(
        firefox_desktop, "PrivateDesktopFirefoxService"
    ), patch.object(browser, "_firefox_executable", return_value="firefox.exe"):
        browser._launch_firefox(tmp_path, headed=False)
    prefs = launch.call_args.kwargs["options"].preferences
    assert prefs["layers.acceleration.disabled"] is False
    assert prefs["layers.gpu-process.enabled"] is True
    assert prefs["gfx.webrender.software"] is False
    assert prefs["gfx.webrender.software.d3d11"] is True


def test_no_behavior_change_until_private_desktop_is_enabled(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYSIS_PRIVATE_DESKTOP")
    with patch("selenium.webdriver.Firefox") as launch, patch.object(
        firefox_desktop, "PrivateDesktopFirefoxService"
    ) as service, patch.object(browser, "_firefox_executable", return_value="firefox.exe"), patch.object(
        browser, "_hide_selenium_firefox_window", return_value=True
    ) as hide:
        browser._launch_firefox(tmp_path, headed=False)
    service.assert_not_called()
    hide.assert_called_once_with(launch.return_value)
    prefs = launch.call_args.kwargs["options"].preferences
    assert prefs["layers.acceleration.disabled"] is False
    assert prefs["layers.gpu-process.enabled"] is True
    assert prefs["gfx.webrender.software"] is False
    assert prefs["gfx.webrender.software.d3d11"] is True


def test_failed_private_desktop_never_launches_interactive_fallback(tmp_path):
    error = RuntimeError("chatgpt_firefox_launch_failed: Browsing context has been discarded")
    with patch.object(browser, "_launch_firefox", side_effect=error) as launch, patch.object(
        browser, "_stop_orphaned_firefox_profile_processes"
    ), patch.object(browser, "_clear_firefox_profile_runtime_locks"), patch.object(browser.time, "sleep"):
        with pytest.raises(RuntimeError, match="discarded"):
            browser._launch_firefox_with_retries(tmp_path, headed=False)
    assert len(launch.call_args_list) > 1
    assert all(call.kwargs["headed"] is False for call in launch.call_args_list)


def test_desktop_is_released_when_process_creation_fails():
    with patch.object(firefox_desktop, "PrivateDesktop") as desktop, patch.object(
        firefox_desktop, "DesktopProcess", side_effect=OSError("cannot start")
    ):
        service = firefox_desktop.PrivateDesktopFirefoxService()
        with pytest.raises(OSError, match="cannot start"):
            service._start_process("geckodriver.exe")
        desktop.return_value.close.assert_called_once_with()
        assert service.desktop is None
        service.stop()


def test_service_releases_process_and_desktop_after_shutdown():
    service = firefox_desktop.PrivateDesktopFirefoxService()
    process = Mock()
    process.poll.return_value = 0
    service.process = process
    desktop = service.desktop = Mock()
    service.stop()
    service.stop()
    process.close.assert_called_once_with()
    desktop.close.assert_called_once_with()


def test_native_creation_selects_desktop_and_restricts_inherited_handles(tmp_path):
    kernel = Mock()
    api = Mock()
    api.DuplicateHandle.side_effect = [101, 102]

    def init_attributes(buffer, count, flags, size):
        ctypes.cast(size, ctypes.POINTER(ctypes.c_size_t))[0] = 64
        return buffer is not None

    kernel.InitializeProcThreadAttributeList.side_effect = init_attributes

    def create(executable, command, process_sa, thread_sa, inherit, flags,
               environment, cwd, startup_pointer, info_pointer):
        startup = ctypes.cast(startup_pointer, ctypes.POINTER(windows_desktop._StartupInfoEx)).contents
        assert startup.StartupInfo.lpDesktop == "private-test-desktop"
        assert startup.StartupInfo.hStdInput == 101
        assert startup.StartupInfo.hStdOutput == startup.StartupInfo.hStdError == 102
        assert startup.StartupInfo.cb == ctypes.sizeof(windows_desktop._StartupInfoEx)
        assert flags & 0x00080000
        assert flags & subprocess.CREATE_NO_WINDOW
        assert inherit is True
        info = ctypes.cast(info_pointer, ctypes.POINTER(windows_desktop._ProcessInfo)).contents
        info.hProcess, info.hThread, info.dwProcessId = 201, 202, 203
        return True

    kernel.CreateProcessW.side_effect = create
    desktop = Mock()
    desktop.name = "private-test-desktop"
    with patch.object(windows_desktop.ctypes, "WinDLL", return_value=kernel), patch.dict(
        sys.modules, {"_winapi": api}
    ), (tmp_path / "log.txt").open("w") as log:
        process = windows_desktop.DesktopProcess(
            ["cmd.exe", "/c", "test.bat"], desktop=desktop, env={}, stdout=log,
        )
        assert process.pid == 203
        attribute_args = kernel.UpdateProcThreadAttribute.call_args.args
        assert list(attribute_args[3]) == [101, 102]
        assert {call.args[0] for call in api.CloseHandle.call_args_list} == {101, 102, 202}
        kernel.DeleteProcThreadAttributeList.assert_called_once()
        process.close()


def test_native_firefox_service_creation_has_no_inherited_handles():
    kernel = Mock()
    api = Mock()
    desktop = Mock()
    desktop.name = "private-firefox"

    def create(*args):
        startup = ctypes.cast(args[8], ctypes.POINTER(windows_desktop._StartupInfo)).contents
        assert startup.lpDesktop == "private-firefox"
        assert args[4] is False
        assert args[5] & subprocess.CREATE_NO_WINDOW
        assert not (args[5] & 0x00080000)
        info = ctypes.cast(args[9], ctypes.POINTER(windows_desktop._ProcessInfo)).contents
        info.hProcess, info.hThread, info.dwProcessId = 301, 302, 303
        return True

    kernel.CreateProcessW.side_effect = create
    with patch.object(windows_desktop.ctypes, "WinDLL", return_value=kernel), patch.dict(
        sys.modules, {"_winapi": api}
    ):
        process = windows_desktop.DesktopProcess(["geckodriver.exe"], desktop=desktop, env={})
        assert process.pid == 303
        process.close()
    api.DuplicateHandle.assert_not_called()


def test_persistent_installation_setting_enables_isolation(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYSIS_PRIVATE_DESKTOP")
    directory = tmp_path / ".local"
    directory.mkdir()
    (directory / "background_windows.json").write_text(json.dumps({"firefox": True, "ibkr": True}))
    assert windows_desktop.private_desktop_enabled("firefox", directory / "profiles")
    assert windows_desktop.private_desktop_enabled("ibkr", directory)


def test_setting_preserves_explicit_opt_out(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALYSIS_PRIVATE_DESKTOP", "0")
    directory = tmp_path / ".local"
    directory.mkdir()
    (directory / "background_windows.json").write_text(json.dumps({"firefox": True, "ibkr": True}))
    assert not windows_desktop.private_desktop_enabled("firefox", directory)
    assert not windows_desktop.private_desktop_enabled("ibkr", directory)


def test_non_windows_does_not_enable_win32_isolation(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYSIS_PRIVATE_DESKTOP")
    with patch.object(windows_desktop.os, "name", "posix"):
        assert not windows_desktop.private_desktop_enabled("firefox", tmp_path)


def test_invalid_background_setting_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYSIS_PRIVATE_DESKTOP")
    directory = tmp_path / ".local"
    directory.mkdir()
    (directory / "background_windows.json").write_text('{"firefox":"yes"}')
    with pytest.raises(RuntimeError, match="background_windows_config_invalid"):
        windows_desktop.private_desktop_enabled("firefox", directory)


def test_background_setting_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYSIS_PRIVATE_DESKTOP")
    directory = tmp_path / ".local"
    directory.mkdir()
    config = directory / "background_windows.json"
    config.write_text('{"firefox":false}')
    assert not windows_desktop.private_desktop_enabled("firefox", directory)
    config.write_text('{"firefox":true}')
    assert windows_desktop.private_desktop_enabled("firefox", directory)


def test_persistent_setting_routes_firefox_to_private_service(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYSIS_PRIVATE_DESKTOP")
    directory = tmp_path / ".local"
    directory.mkdir()
    (directory / "background_windows.json").write_text('{"firefox":true}')
    with patch("selenium.webdriver.Firefox") as launch, patch.object(
        firefox_desktop, "PrivateDesktopFirefoxService"
    ) as service, patch.object(browser, "_firefox_executable", return_value="firefox.exe"):
        browser._launch_firefox(directory / "worker-profile", headed=False)
    assert launch.call_args.kwargs["service"] is service.return_value


def test_persistent_setting_prevents_visible_recovery(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYSIS_PRIVATE_DESKTOP")
    directory = tmp_path / ".local"
    directory.mkdir()
    (directory / "background_windows.json").write_text('{"firefox":true}')
    error = RuntimeError("chatgpt_firefox_launch_failed: Browsing context has been discarded")
    with patch.object(browser, "_launch_firefox", side_effect=error) as launch, patch.object(
        browser, "_stop_orphaned_firefox_profile_processes"
    ), patch.object(browser, "_clear_firefox_profile_runtime_locks"), patch.object(browser.time, "sleep"):
        with pytest.raises(RuntimeError, match="discarded"):
            browser._launch_firefox_with_retries(directory / "worker-profile", headed=False)
    assert all(call.kwargs["headed"] is False for call in launch.call_args_list)


def test_persistent_setting_routes_gateway_to_private_launcher(tmp_path, monkeypatch):
    monkeypatch.delenv("ANALYSIS_PRIVATE_DESKTOP")
    prepare_fake_gateway(tmp_path)
    (tmp_path / ".local/background_windows.json").write_text('{"ibkr":true}')
    with patch.object(gateway, "is_gateway_available", side_effect=[False, True]), patch.object(
        gateway, "_stop_stale_ibkr_processes"
    ), patch.object(gateway.time, "sleep"), patch.object(
        windows_desktop, "start_private_desktop_process"
    ) as launch:
        assert gateway.ensure_gateway(tmp_path) == "started"
    launch.assert_called_once()


def test_service_passes_diagnostic_file_to_native_process(tmp_path):
    with patch.object(firefox_desktop, "PrivateDesktop"), patch.object(
        firefox_desktop, "DesktopProcess"
    ) as launch:
        service = firefox_desktop.PrivateDesktopFirefoxService(log_output=str(tmp_path / "driver.log"))
        service._start_process("geckodriver.exe")
        assert launch.call_args.kwargs["stdout"] is service.log_output
        service.stop()


def test_gateway_already_running_is_untouched_even_when_isolation_enabled(tmp_path):
    with patch.object(gateway, "is_gateway_available", return_value=True), patch.object(
        windows_desktop, "start_private_desktop_process"
    ) as launch, patch.object(gateway, "_stop_stale_ibkr_processes") as stop:
        assert gateway.ensure_gateway(tmp_path) == "already_running"
    launch.assert_not_called()
    stop.assert_not_called()


def prepare_fake_gateway(root):
    for relative in (
        ".local/ibc/scripts/StartIBC.bat", ".local/ibc/IBC.jar",
        ".local/ibgateway/ibgateway-offline/ibgateway.vmoptions", "secrets/ibc/config.ini",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


def test_gateway_private_launch_preserves_log_and_uses_no_desktop_clicks(tmp_path):
    prepare_fake_gateway(tmp_path)
    with patch.object(gateway, "is_gateway_available", side_effect=[False, True]), patch.object(
        gateway, "_stop_stale_ibkr_processes"
    ), patch.object(gateway.time, "sleep"), patch.object(
        gateway, "_dismiss_gateway_settings_recovery_dialog"
    ) as click, patch.object(windows_desktop, "start_private_desktop_process") as launch:
        assert gateway.ensure_gateway(tmp_path) == "started"
    assert launch.call_args.kwargs["label"] == "ibkr"
    assert launch.call_args.kwargs["stdout"].name.endswith(".log")
    assert "/Mode:paper" in launch.call_args.args[0]
    click.assert_not_called()


def test_gateway_recovery_still_uses_log_when_dialog_is_off_desktop(tmp_path):
    prepare_fake_gateway(tmp_path)
    with patch.object(gateway, "is_gateway_available", return_value=False), patch.object(
        gateway, "_stop_stale_ibkr_processes"
    ), patch.object(gateway, "_log_reports_settings_recovery", return_value=True), patch.object(
        gateway, "_recover_rejected_profile", return_value="profile_recreated:started"
    ) as recover, patch.object(windows_desktop, "start_private_desktop_process") as launch:
        assert gateway.ensure_gateway(tmp_path) == "profile_recreated:started"
    assert recover.call_args.args[1] is launch.return_value


def test_private_desktop_failure_does_not_fall_back_to_visible_gateway(tmp_path):
    prepare_fake_gateway(tmp_path)
    with patch.object(gateway, "is_gateway_available", return_value=False), patch.object(
        gateway, "_stop_stale_ibkr_processes"
    ), patch.object(windows_desktop, "start_private_desktop_process", side_effect=OSError("denied")), patch.object(
        gateway.subprocess, "Popen"
    ) as visible:
        with pytest.raises(RuntimeError, match="private_desktop_launch_failed"):
            gateway.ensure_gateway(tmp_path)
    visible.assert_not_called()
