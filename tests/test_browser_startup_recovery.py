import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from src.local_runner import chatgpt_browser_generator as browser

class BrowserStartupRecoveryTests(unittest.TestCase):
    def test_reasoning_trigger_without_old_data_hooks(self):
        trigger = Mock()
        trigger.text = 'Esfuerzo de razonamiento'
        trigger.is_displayed.return_value = True
        trigger.get_attribute.side_effect = {'title': 'Esfuerzo de razonamiento'}.get
        self.assertTrue(browser._is_selenium_reasoning_trigger(trigger))

    def test_simple_picker_verifies_sol_and_keyboard_effort(self):
        from selenium.webdriver.common.keys import Keys
        state = {'open': False, 'advanced': False, 'sol': False, 'effort': 4}
        trigger, toggle, slider, keyboard, sol, body = [Mock() for _ in range(6)]
        trigger.text = 'Esfuerzo de razonamiento'
        trigger.get_attribute.side_effect = lambda name: {'title': 'Esfuerzo de razonamiento', 'aria-expanded': str(state['open']).lower()}.get(name)
        trigger.send_keys.side_effect = lambda *a: state.update(open=True)
        toggle.get_attribute.side_effect = lambda name: str(state['advanced']).lower() if name == 'aria-expanded' else None
        toggle.click.side_effect = lambda: state.update(advanced=not state['advanced'])
        sol.text = 'GPT-5.6 Sol'
        sol.get_attribute.side_effect = lambda name: str(state['sol']).lower() if name == 'aria-checked' else None
        sol.is_displayed.side_effect = lambda: state['advanced']
        slider.get_attribute.side_effect = lambda name: str(state['effort']) if name == 'aria-valuenow' else None
        def adjust(keys):
            for key in keys:
                state['effort'] = max(0, min(4, state['effort'] + (1 if key == Keys.ARROW_RIGHT else -1)))
        keyboard.send_keys.side_effect = adjust
        driver = Mock()
        def elements(by, selector):
            if selector.startswith('button['):
                return [trigger]
            if not state['open']:
                return []
            if selector == "[role='menuitemradio']":
                return [sol]
            if selector == "[role='slider']":
                return [slider]
            if 'aria-keyshortcuts' in selector:
                return [keyboard] if not state['advanced'] else []
            if 'Seleccionar modelo' in selector:
                return [toggle]
            if 'data-model-reasoning-effort-slider' in selector:
                return [keyboard]
            return []
        driver.find_elements.side_effect = elements
        driver.find_element.return_value = body
        driver.execute_script.side_effect = lambda *a: state.update(sol=True)
        browser._ensure_selenium_sol_high(driver, timeout_seconds=1)
        self.assertTrue(state['sol'])
        self.assertEqual(state['effort'], 2)
        self.assertEqual(toggle.click.call_count, 2)
        body.send_keys.assert_called_with(Keys.ESCAPE)

    def test_missing_composer_recovers_and_retries_are_bounded(self):
        error = RuntimeError('chatgpt_firefox_navigation_failed: prompt_not_available')
        for recovers in (True, False):
            with self.subTest(recovers=recovers), TemporaryDirectory() as folder:
                session = browser.ChatGPTBrowserSession(Path(folder), browser_engine='firefox')
                failures = [error, None] if recovers else error
                with patch.object(browser, '_launch_firefox_with_retries', side_effect=lambda *a, **k: Mock()) as launch, patch.object(browser, '_ensure_selenium_authenticated', side_effect=failures) as auth, patch.object(browser, '_write_selenium_trace') as trace, patch.object(browser.time, 'sleep'):
                    if recovers:
                        session.open()
                        self.assertTrue(session.is_open)
                        self.assertEqual(auth.call_count, 2)
                        self.assertEqual(trace.call_count, 1)
                        session.close()
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'prompt_not_available'):
                            session.open()
                        self.assertEqual(launch.call_count, 1 + browser.DEFAULT_TRANSIENT_OPEN_RETRIES)
                        self.assertEqual(trace.call_count, launch.call_count)
                        self.assertFalse(session.is_open)
                    self.assertTrue(trace.call_args.kwargs['capture_page'])

    def test_failed_composer_preserves_healthy_workers(self):
        with TemporaryDirectory() as folder:
            sessions = tuple(Mock(cwd=Path(folder).resolve(), engine='firefox', worker_id=i, chat_group_size=5) for i in (1, 2))
            sessions[1].open.side_effect = RuntimeError('chatgpt_firefox_navigation_failed: prompt_not_available')
            pool = browser.ChatGPTBrowserSessionPool(Path(folder), worker_count=2, browser_engine='firefox', sessions=sessions)
            pool.preflight()
            self.assertEqual(pool.worker_count, 1)
            self.assertEqual(pool.disabled_worker_ids, (2,))
            self.assertEqual(pool.sessions, (sessions[0],))
            sessions[1].close.assert_called_once()

if __name__ == '__main__':
    unittest.main()
