"""Exercise the Streamlit workflow without using a real API key or network."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / 'app.py'


class WorkspaceTests(unittest.TestCase):
    def app(self):
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        return app

    def button(self, app, label):
        return next(b for b in app.button if b.label == label)

    def fake_client(self, text):
        client = MagicMock()
        client.__enter__.return_value = client
        client.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(type='text', text=text)], stop_reason='end_turn')
        return client

    def test_manual_key_and_required_inputs(self):
        app = self.app()
        self.assertEqual(app.selectbox(key='grade').value, 'Grade 11')
        self.assertFalse(any('Pip' in x.value for x in app.markdown))
        app.text_input(key='api_key_input').set_value('test-key').run()
        self.button(app, 'Get analytical feedback').click().run()
        self.assertIn('source text', app.error[0].value)
        self.assertNotIn('API key', app.error[0].value)

    def test_generation_requires_key(self):
        app = self.app()
        app.selectbox(key='assignment_mode').select('Generate a practice source and question').run()
        self.button(app, 'Generate missing material').click().run()
        self.assertIn('Enter an Anthropic key', app.error[0].value)

    def test_generate_source_preserves_question_and_calibrates_grade(self):
        client = self.fake_client(json.dumps({'source': 'An original practice passage.', 'question': 'Ignored replacement'}))
        with patch('anthropic.Anthropic', return_value=client):
            app = self.app()
            app.text_input(key='api_key_input').set_value('test-key').run()
            app.selectbox(key='grade').select('Grade 7').run()
            app.selectbox(key='assignment_mode').select('Generate a practice source and question').run()
            app.text_input(key='question').set_value('How does the speaker change?').run()
            self.button(app, 'Generate missing material').click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.text_input(key='question').value, 'How does the speaker change?')
            self.assertEqual(app.text_area(key='source_text').value, 'An original practice passage.')
            sent = json.loads(client.messages.create.call_args.kwargs['messages'][0]['content'])
            self.assertEqual(sent['grade'], 'Grade 7')
            self.assertTrue(sent['generate_source'])
            self.assertFalse(sent['generate_question'])
            self.button(app, 'Generate missing material').click().run()
            self.assertIn('Both fields already have content', app.error[0].value)
            self.assertEqual(client.messages.create.call_count, 1)

    def test_generate_question_preserves_source_and_rejects_bad_response(self):
        client = self.fake_client(json.dumps({'source': 'Ignored replacement', 'question': 'How is the claim developed?'}))
        with patch('anthropic.Anthropic', return_value=client):
            app = self.app()
            app.text_input(key='api_key_input').set_value('test-key').run()
            app.selectbox(key='assignment_mode').select('Generate a question from my source').run()
            app.text_area(key='source_text').set_value('My original source.').run()
            self.button(app, 'Generate missing material').click().run()
            self.assertEqual(app.text_area(key='source_text').value, 'My original source.')
            self.assertEqual(app.text_input(key='question').value, 'How is the claim developed?')
            app.text_input(key='question').set_value('').run()
            client.messages.create.return_value.content[0].text = 'invalid JSON'
            self.button(app, 'Generate missing material').click().run()
            self.assertIn('expected format', app.error[0].value)
            self.assertEqual(app.text_input(key='question').value, '')
            self.assertEqual(app.text_area(key='source_text').value, 'My original source.')

    def test_generate_complete_assignment(self):
        client = self.fake_client(json.dumps({'source': 'A new practice source.', 'question': 'What does this choice reveal?'}))
        with patch('anthropic.Anthropic', return_value=client):
            app = self.app()
            app.text_input(key='api_key_input').set_value('test-key').run()
            app.selectbox(key='assignment_mode').select('Generate a practice source and question').run()
            self.button(app, 'Generate missing material').click().run()
            self.assertEqual(app.text_area(key='source_text').value, 'A new practice source.')
            self.assertEqual(app.text_input(key='question').value, 'What does this choice reveal?')
            sent = json.loads(client.messages.create.call_args.kwargs['messages'][0]['content'])
            self.assertTrue(sent['generate_source'])
            self.assertTrue(sent['generate_question'])

    def test_connection_error_keeps_writing_and_hides_exception(self):
        client = self.fake_client('unused')
        client.messages.create.side_effect = RuntimeError('private failure detail')
        with patch('anthropic.Anthropic', return_value=client):
            app = self.app()
            app.text_input(key='api_key_input').set_value('test-key').run()
            app.text_area(key='source_text').set_value('My source.').run()
            app.text_area(key='paragraph').set_value('My paragraph.').run()
            self.button(app, 'Get analytical feedback').click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.text_area(key='paragraph').value, 'My paragraph.')
            self.assertNotIn('private failure detail', app.error[0].value)
            self.assertNotIn('test-key', app.error[0].value)

    def test_feedback_includes_question_persists_and_marks_edits(self):
        client = self.fake_client('## Score\n7/10\n\n## Next revision steps\nExplain your evidence.')
        with patch('anthropic.Anthropic', return_value=client):
            app = self.app()
            app.text_input(key='api_key_input').set_value('test-key').run()
            app.text_input(key='question').set_value('Why does the choice matter?').run()
            app.text_area(key='source_text').set_value('The speaker chooses to help.').run()
            app.text_area(key='paragraph').set_value('The choice reveals compassion because it costs the speaker time.').run()
            self.button(app, 'Get analytical feedback').click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn('Why does the choice matter?', client.messages.create.call_args.kwargs['messages'][0]['content'])
            self.assertIn('Grade-level calibration', client.messages.create.call_args.kwargs['system'])
            self.assertIn('7/10', app.session_state['feedback'])
            app.text_area(key='paragraph').set_value('A revised paragraph.').run()
            self.assertIn('earlier submission', app.warning[0].value)
            self.assertIn('7/10', app.session_state['feedback'])
            self.assertEqual(client.messages.create.call_count, 1)


if __name__ == '__main__':
    unittest.main()
