'use strict';
const $ = id => document.getElementById(id);
const fields = ['grade', 'class_level', 'model', 'question', 'source', 'paragraph', 'extra', 'topic', 'mode'];
let config, feedback = '', feedbackSnapshot = '', generatedSource = '', busy = false;
const payload = () => Object.fromEntries(fields.map(id => [id, $(id).value]));
const snapshot = () => JSON.stringify(Object.fromEntries(fields.filter(id => !['topic', 'mode'].includes(id)).map(id => [id, $(id).value])));
function message(id, text, kind = 'error') {
  const el = $(id); el.textContent = text; el.className = `message ${kind}`; el.hidden = !text;
}
function update() {
  const text = $('paragraph').value;
  $('word-count').textContent = `${text.trim() ? text.trim().split(/\s+/u).length : 0} words · ${text.length} characters`;
  $('generation-controls').hidden = $('mode').value === 'own';
  $('generated-note').hidden = !generatedSource || generatedSource !== $('source').value;
  $('stale-note').hidden = !feedback || snapshot() === feedbackSnapshot;
  $('key-status').textContent = $('api-key').value.trim() ? 'Key entered · only held in this tab.' : 'Only held in this tab. Never saved to browser storage.';
  if (config) {
    $('criteria-title').textContent = `Expectations for ${$('grade').value}`;
    $('grade-criteria').textContent = config.grade_criteria[$('grade').value];
    $('class-criteria').textContent = config.class_criteria[$('class_level').value];
  }
}
function setBusy(value, action) {
  busy = value;
  $('generate').disabled = value || !config;
  $('grade-button').disabled = value || !config;
  $('generate').textContent = value && action === 'generate' ? 'Preparing your assignment…' : '✦ Generate missing material';
  $('grade-button').textContent = value && action === 'feedback' ? 'Reading your evidence and reasoning…' : 'Get analytical feedback →';
  $(action === 'generate' ? 'generation-controls' : 'feedback-panel').setAttribute('aria-busy', String(value));
}
async function request(path, data) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 130000);
  try {
    const response = await fetch(`/api/${path}`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Anthropic-Key': $('api-key').value.trim()}, body: JSON.stringify(data), signal: controller.signal});
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Check the selected levels and input lengths, then try again.');
    return result;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The request took too long. Your writing is kept; try again.');
    if (error instanceof TypeError || error instanceof SyntaxError) throw new Error('Could not reach the server. Your writing is kept; try again.');
    throw error;
  } finally { clearTimeout(timeout); }
}
// Render a small Markdown subset using DOM nodes. API output is never injected as HTML.
function appendInline(parent, text) {
  text.split(/(\*\*[^*]+\*\*)/g).forEach(part => {
    if (part.startsWith('**') && part.endsWith('**')) {const strong = document.createElement('strong'); strong.textContent = part.slice(2,-2); parent.append(strong);}
    else parent.append(document.createTextNode(part));
  });
}
function renderFeedback(text) {
  const container = $('feedback-content'); container.replaceChildren(); let list = null;
  for (const line of text.split('\n')) {
    if (!line.trim()) {list = null; continue;}
    const heading = line.match(/^#{1,6}\s+(.+)/);
    const item = line.match(/^\s*(?:[-*]|\d+[.)])\s+(.+)/);
    if (item) {if (!list) {list = document.createElement('ul'); container.append(list);} const li = document.createElement('li'); appendInline(li,item[1]); list.append(li);}
    else {list = null; const node = document.createElement(heading ? 'h3' : 'p'); appendInline(node, heading ? heading[1] : line); container.append(node);}
  }
  container.hidden = false; $('feedback-empty').hidden = true; $('download').hidden = false;
}
$('generate').addEventListener('click', async () => {
  if (busy) return;
  message('generation-message', ''); const data = payload();
  if (!$('api-key').value.trim()) return message('generation-message', 'Enter your Anthropic key in the classroom panel.');
  if (data.source.trim() && data.question.trim()) return message('generation-message', 'Both fields already have content. Clear the field you want to generate.');
  if (data.mode === 'question' && !data.source.trim()) return message('generation-message', 'Paste source text first, or choose a practice source and question.');
  setBusy(true, 'generate');
  try {
    const result = await request('generate', data);
    if (['grade','class_level','model','topic','mode','source','question'].some(id => $(id).value !== data[id])) {
      message('generation-message', 'Assignment settings or text changed while generating. Your edits were kept; generate again.', 'warning'); return;
    }
    if (result.generated_source) { $('source').value = result.source; generatedSource = result.source; }
    if (result.generated_question) $('question').value = result.question;
    update(); message('generation-message', 'Assignment ready. Review and edit it before writing.', 'success');
  } catch (error) { message('generation-message', error.message); }
  finally {setBusy(false, 'generate');}
});
$('grade-button').addEventListener('click', async () => {
  if (busy) return;
  message('feedback-message', '');
  const data = payload(), submittedSnapshot = snapshot();
  if (!$('api-key').value.trim()) return message('feedback-message', 'Enter your Anthropic key in the classroom panel.');
  if (!data.source.trim() || !data.paragraph.trim()) return message('feedback-message', 'Add both source text and an analytical paragraph.');
  setBusy(true, 'feedback');
  try {
    const result = await request('feedback', data); feedback = result.feedback; feedbackSnapshot = submittedSnapshot;
    renderFeedback(feedback); update(); $('feedback-panel').scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) { message('feedback-message', error.message); }
  finally {setBusy(false, 'feedback');}
});
$('toggle-key').addEventListener('click', () => {
  const show = $('api-key').type === 'password'; $('api-key').type = show ? 'text' : 'password';
  $('toggle-key').textContent = show ? 'Hide' : 'Show'; $('toggle-key').setAttribute('aria-label', show ? 'Hide API key' : 'Show API key'); $('toggle-key').setAttribute('aria-pressed', String(show));
});
$('download').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([feedback], {type: 'text/markdown;charset=utf-8'}));
  const link = document.createElement('a'); link.href = url; link.download = 'analytical-feedback.md'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
[...fields, 'api-key'].forEach(id => {$(id).addEventListener('input',update); $(id).addEventListener('change',update);});
async function initialize() {
  try {
    const response = await fetch('/api/config'); if (!response.ok) throw new Error(); config = await response.json();
    for (const [id, options, selected] of [['grade',config.grades,'Grade 11'],['class_level',config.classes,'On-level / regular']]) {
      $(id).replaceChildren(...options.map(value => {const option = document.createElement('option'); option.value = value; option.textContent = value; return option;}));
      $(id).value = selected; $(id).disabled = false;
    }
    $('model').value = config.model; $('core-criteria').textContent = config.core_criteria; setBusy(false,'feedback'); update();
  } catch {message('feedback-message','The classroom settings could not load. Refresh the page to retry.');}
}
initialize();
