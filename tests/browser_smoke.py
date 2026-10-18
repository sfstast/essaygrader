"""Real browser checks against an isolated server, with AI routes mocked."""
import json
import os
import shutil
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'server:app', '--host', '127.0.0.1', '--port', str(port)],
                          cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
base = f'http://127.0.0.1:{port}'
try:
    for attempt in range(100):
        try:
            with urlopen(base + '/api/health', timeout=1) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(.1)
    else:
        raise RuntimeError('Test server did not start')
    with sync_playwright() as p:
        executable = os.getenv('BROWSER_EXECUTABLE') or shutil.which('chromium')
        browser = p.chromium.launch(headless=True, executable_path=executable)
        page = browser.new_page(viewport={'width': 1440, 'height': 1080})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base)
        page.wait_for_function("document.getElementById('grade').disabled === false")
        assert page.locator('#welcome').is_visible()
        page.locator('#learning-goal').fill('Explain my evidence clearly.')
        page.locator('#start-learning').click()
        assert page.locator('#writing-tools').is_visible()
        assert page.locator('#grade').input_value() == 'Grade 11'
        page.locator('#grade-button').click()
        assert 'Anthropic key' in page.locator('#feedback-message').inner_text()
        page.locator('#api-key').fill('test-key')
        page.locator('#mode').select_option('both')
        page.locator('#grade').select_option('Grade 7')
        def generation(route):
            data = route.request.post_data_json
            assert data['grade'] == 'Grade 7'
            route.fulfill(json={'source': 'Original practice text.', 'question': 'Why does the speaker help?',
                                'generated_source': True, 'generated_question': True})
        page.route('**/api/generate', generation)
        page.locator('#generate').click()
        page.wait_for_function("document.getElementById('source').value === 'Original practice text.'")
        assert page.locator('#question').input_value() == 'Why does the speaker help?'
        page.locator('#paragraph').fill('The speaker shows compassion because helping costs them time.')
        assert '9 words' in page.locator('#word-count').inner_text()
        assert page.evaluate('localStorage.length') == 0
        assert page.evaluate('sessionStorage.length') == 0
        feedback_calls = []
        def grading(route):
            feedback_calls.append(route.request.post_data_json)
            assert 'speaker' in route.request.post_data_json['question']
            route.fulfill(json={'feedback': '## Score\n7/10\n\n**Good evidence.**\n<script>window.unsafe=true</script>'})
        page.route('**/api/feedback', grading)
        page.locator('#grade-button').click()
        page.locator('#feedback-content').wait_for(state='visible')
        assert '7/10' in page.locator('#feedback-content').inner_text()
        assert page.locator('#feedback-content strong').inner_text() == 'Good evidence.'
        assert page.evaluate('window.unsafe') is None
        page.locator('#grade-button').click()
        assert 'existing feedback' in page.locator('#feedback-message').inner_text()
        assert len(feedback_calls) == 1
        page.locator('#paragraph').fill('My revision.')
        assert page.locator('#stale-note').is_visible()
        with page.expect_download() as download:
            page.locator('#download').click()
        assert download.value.suggested_filename == 'analytical-feedback.md'
        assert page.locator('#provider').input_value() == 'anthropic'
        assert page.locator('#model option').count() == 5
        page.locator('#model').select_option('claude-sonnet-5-5')
        assert page.locator('#api-key').input_value() == 'test-key'
        def tutoring(route):
            data = route.request.post_data_json
            assert data['provider'] == 'anthropic'
            assert data['grade'] == 'Grade 7'
            assert route.request.headers['x-model-key'] == 'test-key'
            route.fulfill(json={'reply':'Focus on why the volunteer stays. What does that reveal about their motive?'})
        page.route('**/api/tutor',tutoring)
        page.locator('#tutor-question').fill('How can I explain my evidence?')
        page.locator('#tutor-send').click()
        page.wait_for_function("document.querySelectorAll('.tutor-turn').length === 2")
        assert 'volunteer' in page.locator('#tutor-conversation').inner_text()
        page.locator('#paragraph').fill('A new revised paragraph.')
        assert page.locator('.tutor-turn').count() == 0
        assert 'new tutoring conversation' in page.locator('#tutor-message').inner_text()
        page.locator('summary',has_text='Teacher instructions & grading criteria').click()
        with page.expect_download() as review_download:
            page.locator('#review-template').click()
        template = json.loads(Path(review_download.value.path()).read_text())
        assert template['teacher_scores'][0]['score'] is None
        assert template['permission_to_use'] is False
        assert template['commercial_use_allowed'] is False
        assert template['paragraph'] == 'A new revised paragraph.'
        page.locator('summary',has_text='Teacher instructions & grading criteria').click()
        page.evaluate('scrollTo(0, 0)')
        page.wait_for_timeout(350)
        page.screenshot(path='/tmp/reasoning-studio-desktop.png', full_page=True)
        page.locator('a[aria-label="Reasoning Studio home"]').click()
        page.screenshot(path='/tmp/reasoning-studio-welcome.png', full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.evaluate('scrollTo(0, 0)')
        page.wait_for_timeout(350)
        page.screenshot(path='/tmp/reasoning-studio-mobile.png', full_page=True)
        assert not errors, errors
        browser.close()
    print('PASS browser: rendering, manual key, generation, grading, word count, safe feedback, stale notice, download, Claude-only models, tutoring, teacher review export, mobile layout')
finally:
    server.terminate()
    server.wait(timeout=10)
