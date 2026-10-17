'use strict';
const $ = id => document.getElementById(id);
const fields = ['provider', 'grade', 'class_level', 'model', 'question', 'source', 'paragraph', 'extra', 'topic', 'mode'];
let config, feedback = '', feedbackSnapshot = '', generatedSource = '', busy = false;
let tutorHistory = [], tutorSnapshot = '';
const providerDetails = () => config?.providers?.find(p => p.id === $('provider').value);
const keyName = () => providerDetails()?.key_label || 'Anthropic key';
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
  if (tutorHistory.length && snapshot() !== tutorSnapshot) {
    tutorHistory = []; $('tutor-conversation').replaceChildren();
    message('tutor-message', 'Assignment or settings changed. Your next question starts a new tutoring conversation.', 'warning');
  }
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
  $('tutor-send').disabled = value || !config;
  $('tutor-send').textContent = value && action === 'tutor' ? 'Thinking about your next step…' : 'Ask for a writing hint';
  $('generate').textContent = value && action === 'generate' ? 'Preparing your assignment…' : '✦ Generate missing material';
  $('grade-button').textContent = value && action === 'feedback' ? 'Reading your evidence and reasoning…' : 'Get analytical feedback →';
  $(action === 'generate' ? 'generation-controls' : action === 'tutor' ? 'tutor-panel' : 'feedback-panel').setAttribute('aria-busy', String(value));
}
async function request(path, data) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 130000);
  try {
    const response = await fetch(`/api/${path}`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Model-Key': $('api-key').value.trim()}, body: JSON.stringify(data), signal: controller.signal});
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
  if (!$('api-key').value.trim()) return message('generation-message', `Enter your ${keyName()} in the classroom panel.`);
  if (data.source.trim() && data.question.trim()) return message('generation-message', 'Both fields already have content. Clear the field you want to generate.');
  if (data.mode === 'question' && !data.source.trim()) return message('generation-message', 'Paste source text first, or choose a practice source and question.');
  setBusy(true, 'generate');
  try {
    const result = await request('generate', data);
    if (['provider','grade','class_level','model','topic','mode','source','question'].some(id => $(id).value !== data[id])) {
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
  if (!$('api-key').value.trim()) return message('feedback-message', `Enter your ${keyName()} in the classroom panel.`);
  if (!data.source.trim() || !data.paragraph.trim()) return message('feedback-message', 'Add both source text and an analytical paragraph.');
  setBusy(true, 'feedback');
  try {
    const result = await request('feedback', data); feedback = result.feedback; feedbackSnapshot = submittedSnapshot;
    renderFeedback(feedback); update(); $('feedback-panel').scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) { message('feedback-message', error.message); }
  finally {setBusy(false, 'feedback');}
});
$('provider').addEventListener('change', () => {
  const selected = providerDetails(); if (!selected) return;
  // Never reuse a credential with another provider.
  $('api-key').value = ''; $('api-key').type = 'password';
  $('toggle-key').textContent = 'Show'; $('toggle-key').setAttribute('aria-label', 'Show API key'); $('toggle-key').setAttribute('aria-pressed','false');
  $('key-label').textContent = selected.key_label; $('model').value = selected.model;
  $('api-key').placeholder = selected.id === 'anthropic' ? 'sk-ant-…' : 'Enter provider key';
  $('provider-note').textContent = selected.id === 'open_model' && !selected.configured ?
    'The site owner must configure an open-model server before this option can send requests.' :
    'Uses this provider for generation, grading, and tutoring. Changing provider clears the entered key.';
  update();
});
$('tutor-send').addEventListener('click', async () => {
  if (busy) return;
  message('tutor-message','');
  const data = payload(), submitted = snapshot(), question = $('tutor-question').value.trim();
  if (!$('api-key').value.trim()) return message('tutor-message',`Enter your ${keyName()} in the classroom panel.`);
  if (!data.source.trim() || !data.paragraph.trim()) return message('tutor-message','Add source text and your paragraph before asking for a hint.');
  if (!question) return message('tutor-message','Ask a writing question first.');
  setBusy(true,'tutor');
  try {
    const result = await request('tutor',{...data,student_message:question,history:tutorHistory.slice(-6)});
    if (submitted !== snapshot()) {message('tutor-message','Your assignment changed while the tutor was responding. Ask again for a hint about your updated writing.','warning'); return;}
    tutorSnapshot = submitted;
    tutorHistory.push({role:'user',content:question},{role:'assistant',content:result.reply});
    tutorHistory = tutorHistory.slice(-6);
    const log = $('tutor-conversation'); log.replaceChildren();
    for (const turn of tutorHistory) {
      const box = document.createElement('div'); box.className = 'tutor-turn ' + turn.role;
      const label = document.createElement('strong'); label.textContent = turn.role === 'user' ? 'You' : 'Writing tutor';
      const text = document.createElement('p'); text.textContent = turn.content;
      box.append(label,text); log.append(box);
    }
    if ($('tutor-question').value.trim() === question) $('tutor-question').value = '';
  } catch (error) {message('tutor-message',error.message);}
  finally {setBusy(false,'tutor');}
});
$('toggle-key').addEventListener('click', () => {
  const show = $('api-key').type === 'password'; $('api-key').type = show ? 'text' : 'password';
  $('toggle-key').textContent = show ? 'Hide' : 'Show'; $('toggle-key').setAttribute('aria-label', show ? 'Hide API key' : 'Show API key'); $('toggle-key').setAttribute('aria-pressed', String(show));
});
$('review-template').addEventListener('click', () => {
  const data = payload();
  const review = {id:'REPLACE-example-id',student_id:'REPLACE-anonymous-student-id',assignment_id:'REPLACE-assignment-id',
    grade:data.grade,class_level:data.class_level,task:'grade',source:data.source,question:data.question,paragraph:data.paragraph,
    rubric:'REPLACE with the teacher rubric and 1–10 score anchors.',
    teacher_scores:[{rater_id:'REPLACE-teacher-1',score:null},{rater_id:'REPLACE-teacher-2',score:null}],
    teacher_feedback:'REPLACE with adjudicated teacher feedback, not AI feedback.',student_message:'',subgroup:'unspecified',
    permission_to_use:false,anonymized:false,commercial_use_allowed:false,provenance:'teacher_reviewed'};
  const url = URL.createObjectURL(new Blob([JSON.stringify(review,null,2)],{type:'application/json'}));
  const link = document.createElement('a'); link.href=url;link.download='teacher-review.json';link.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);
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
    $('provider').replaceChildren(...config.providers.map(provider => {const option = document.createElement('option'); option.value = provider.id; option.textContent = provider.label; return option;}));
    $('model').value = config.model; $('core-criteria').textContent = config.core_criteria; setBusy(false,'feedback'); update();
  } catch {message('feedback-message','The classroom settings could not load. Refresh the page to retry.');}
}
initialize();
