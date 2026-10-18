'use strict';
const $ = id => document.getElementById(id);
const fields = ['provider', 'grade', 'class_level', 'model', 'question', 'source', 'paragraph', 'extra', 'topic', 'mode'];
let config, feedback = '', feedbackSnapshot = '', generatedSource = '', busy = false;
let tutorHistory = [], tutorSnapshot = '';
let studyWords = [], vocabResult = null, vocabResultSnapshot = '';
let sentenceData=null, sentenceLoad=null, sentenceFocus=null, identificationDeck=[], currentIdentification=null, identificationAnswered=false, identificationCorrect=0, identificationTried=0;
let sentenceReview=null, sentenceReviewSnapshot='';
let accountState={available:false,user:null}, accountMode='signup', authPopup=null, authPopupTimer=null;
const learningGoal = () => $('learning-goal').value.trim();

const keyName = () => 'Anthropic key';
const hasKey = () => $('api-key').value.trim();
const payload = () => ({...Object.fromEntries(fields.map(id => [id, $(id).value])), learning_goal:learningGoal()});
const snapshot = () => JSON.stringify({...Object.fromEntries(fields.filter(id => !['topic', 'mode'].includes(id)).map(id => [id, $(id).value])), learning_goal:learningGoal()});
function message(id, text, kind = 'error') {
  const el = $(id); el.textContent = text; el.className = `message ${kind}`; el.hidden = !text;
}
function update() {
  $('goal-reminder').textContent = learningGoal() || 'One useful step at a time.';
  updateVocabStale();
  updateSentenceStale();
  updateWelcomeFocus();
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
  $('grade-vocab').disabled = value || !config;
  $('build-vocab').disabled = value || !config;
  $('review-sentence').disabled = value || !config || !sentenceData || !sentenceFocus?.size;
  $('review-sentence').textContent = value && action === 'sentence' ? 'Reading your sentence…' : 'Check my sentence →';
  $('grade-vocab').textContent = value && action === 'vocabulary' ? 'Checking your words…' : 'Check my vocabulary →';
  $('tutor-send').textContent = value && action === 'tutor' ? 'Thinking about your next step…' : 'Ask for a writing hint';
  $('generate').textContent = value && action === 'generate' ? 'Preparing your assignment…' : '✦ Generate missing material';
  $('grade-button').textContent = value && action === 'feedback' ? 'Reading your evidence and reasoning…' : 'Get analytical feedback →';
  $(action === 'generate' ? 'generation-controls' : action === 'tutor' ? 'tutor-panel' : action === 'vocabulary' ? 'vocab-practice' : action === 'sentence' ? 'sentence-write-panel' : 'feedback-panel').setAttribute('aria-busy', String(value));
}
async function request(path, data) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 240000);
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
  if (!hasKey()) return message('generation-message', `Enter your ${keyName()} in the classroom panel.`);
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
  if (!hasKey()) return message('feedback-message', `Enter your ${keyName()} in the classroom panel.`);
  if (!data.source.trim() || !data.paragraph.trim()) return message('feedback-message', 'Add both source text and an analytical paragraph.');
  if (feedback && submittedSnapshot === feedbackSnapshot) {
    message('feedback-message', 'Showing your existing feedback. Revise your writing or settings to request a new review.', 'info');
    $('feedback-panel').scrollIntoView({behavior:'smooth',block:'start'}); return;
  }
  setBusy(true, 'feedback');
  try {
    const result = await request('feedback', data); feedback = result.feedback; feedbackSnapshot = submittedSnapshot;
    const usage = result.usage || {};
    $('usage-note').hidden = !Number.isInteger(usage.output_tokens);
    $('usage-note').textContent = `${result.model || 'Claude'} · ${usage.input_tokens || 0} new input tokens · ${usage.cache_read_input_tokens || 0} cached input tokens · ${usage.cache_creation_input_tokens || 0} cache-write tokens · ${usage.output_tokens || 0} output tokens`;
    renderFeedback(feedback); update(); $('feedback-panel').scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) { message('feedback-message', error.message); }
  finally {setBusy(false, 'feedback');}
});
$('tutor-send').addEventListener('click', async () => {
  if (busy) return;
  message('tutor-message','');
  const data = payload(), submitted = snapshot(), question = $('tutor-question').value.trim();
  if (!hasKey()) return message('tutor-message',`Enter your ${keyName()} in the classroom panel.`);
  if (!data.source.trim() || !data.paragraph.trim()) return message('tutor-message','Add source text and your paragraph before asking for a hint.');
  if (!question) return message('tutor-message','Ask a writing question first.');
  setBusy(true,'tutor');
  try {
    const result = await request('tutor',{...data,student_message:question,history:tutorHistory.slice(-4).map(turn => ({...turn, content:turn.content.slice(0,1800)}))});
    if (submitted !== snapshot()) {message('tutor-message','Your assignment changed while the tutor was responding. Ask again for a hint about your updated writing.','warning'); return;}
    tutorSnapshot = submitted;
    tutorHistory.push({role:'user',content:question},{role:'assistant',content:result.reply});
    tutorHistory = tutorHistory.slice(-4).map(turn => ({...turn, content:turn.content.slice(0,1800)}));
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
    rubric_id:config.training_rubric.id,rubric:config.training_rubric.text,
    teacher_scores:['REPLACE-teacher-1','REPLACE-teacher-2'].map(rater_id => ({rater_id,score:null,criterion_scores:Object.fromEntries(config.training_rubric.criteria.map(key => [key,null]))})),
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
[...fields, 'api-key', 'learning-goal'].forEach(id => {$(id).addEventListener('input',update); $(id).addEventListener('change',update);});
function route() {
  const activity = location.hash === '#vocabulary' ? 'vocabulary' : location.hash === '#sentences' ? 'sentences' : location.hash === '#workspace' ? 'writing' : 'welcome';
  const home = activity === 'welcome';
  $('welcome').hidden = !home; $('workspace').hidden = home; $('workspace-nav').hidden = home;
  $('writing-tools').hidden = activity !== 'writing'; $('vocabulary-tools').hidden = activity !== 'vocabulary'; $('sentence-tools').hidden = activity !== 'sentences';
  if (activity === 'sentences') loadSentenceLab().catch(error=>message('sentence-load-message',error.message));
  for (const [id, active] of [['writing-tab',activity === 'writing'],['vocabulary-tab',activity === 'vocabulary'],['sentences-tab',activity === 'sentences']]) {
    $(id).classList.toggle('active',active);
    if (active) $(id).setAttribute('aria-current','page'); else $(id).removeAttribute('aria-current');
  }
  document.title = home ? 'Reasoning Studio — Find your next step' : activity === 'vocabulary' ? 'Vocabulary practice — Reasoning Studio' : activity === 'sentences' ? 'Sentence lab — Reasoning Studio' : 'Writing workspace — Reasoning Studio';
}
window.addEventListener('hashchange',route);
$('goal-form').addEventListener('submit',async event => {
  event.preventDefault(); if (!config) return;
  const focus = document.querySelector('input[name="focus"]:checked').value;
  if (focus==='sentences') {
    try {await loadSentenceLab(true);} catch(error){return message('goal-message',error.message);}
    if(!sentenceFocus?.size) return message('goal-message','Choose at least one pattern to practice.');
    if(document.querySelector('input[name="focus"]:checked').value!==focus) return;
    $('identify-category').value='selected';identificationDeck=[];nextIdentification();
  }
  $('grade').value=$('welcome-grade').value;
  if (!learningGoal()) $('learning-goal').value = focus === 'vocabulary' ? 'Use new vocabulary with confidence.' : focus === 'sentences' ? 'Use sentence structures and phrases with confidence.' : focus === 'revision' ? 'Make my draft clearer and stronger.' : 'Support my ideas with clear evidence and reasoning.';
  update(); location.hash = focus === 'vocabulary' ? 'vocabulary' : focus === 'sentences' ? 'sentences' : 'workspace';
});
function updateWelcomeFocus() {
  const focus=document.querySelector('input[name="focus"]:checked').value;
  const words={writing:['Let’s give your ideas a little lift.','Build a clear claim and make your evidence count.'],vocabulary:['New words? Let’s make them yours.','Your word list becomes a practice set built around you.'],sentences:['Let’s discover what a sentence can do.','Choose your patterns. Spot them, then make them your own.'],revision:['Small edits. A stronger voice.','Keep what’s working and find one good change to make.']};
  $('mascot-stage').className='mascot-stage focus-'+focus;if($('mascot-says').textContent!==words[focus][0]) $('mascot-says').textContent=words[focus][0];if($('focus-preview').textContent!==words[focus][1]) $('focus-preview').textContent=words[focus][1];
  $('welcome-pattern-picker').hidden=focus!=='sentences';
  document.querySelectorAll('[data-focus-shortcut]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.focusShortcut===focus)));
  const ready=focus!=='sentences' || !!sentenceFocus?.size;
  $('start-learning').disabled=!config || !ready;
  const label=focus==='vocabulary'?'Build my word confidence':focus==='sentences'?(sentenceFocus?.size?`Practice ${sentenceFocus.size} pattern${sentenceFocus.size===1?'':'s'}`:'Choose your patterns'):focus==='revision'?'Find my next revision':'Start my writing practice';
  $('start-learning').textContent=label+' →';
}
document.querySelectorAll('input[name="focus"]').forEach(input=>input.addEventListener('change',()=>{
  updateWelcomeFocus();message('goal-message','');
  if(input.checked && input.value==='sentences') loadSentenceLab(true).catch(error=>message('goal-message',error.message));
}));
document.querySelectorAll('[data-focus-shortcut]').forEach(button=>button.addEventListener('click',()=>{
  const input=document.querySelector(`input[name="focus"][value="${button.dataset.focusShortcut}"]`);input.checked=true;input.dispatchEvent(new Event('change',{bubbles:true}));
}));
$('mascot-stage').addEventListener('pointermove',event=>{
  if(window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const rect=$('mascot-stage').getBoundingClientRect();
  $('mascot-stage').style.setProperty('--look-x',`${Math.max(-3,Math.min(3,(event.clientX-rect.left-rect.width/2)/rect.width*6))}px`);
  $('mascot-stage').style.setProperty('--look-y',`${Math.max(-2,Math.min(2,(event.clientY-rect.top-rect.height/2)/rect.height*4))}px`);
});
$('mascot-stage').addEventListener('pointerleave',()=>{$('mascot-stage').style.setProperty('--look-x','0px');$('mascot-stage').style.setProperty('--look-y','0px');});
$('grade').addEventListener('change',()=>{$('welcome-grade').value=$('grade').value;});
function parseStudyWords(text) {
  const lines=text.split(/\r?\n/).flatMap(line => /[:—–]/u.test(line) ? [line] : line.split(',')).map(line=>line.trim()).filter(Boolean);
  if (!lines.length || lines.length>10) throw new Error('Add between 1 and 10 study words.');
  const words=lines.map(line=>{
    const match=line.match(/^([^:—–]+)[:—–](.*)$/u);
    const word=(match ? match[1] : line).trim(), reference_meaning=(match ? match[2] : '').trim();
    if (!word || word.length>80 || reference_meaning.length>300) throw new Error('Keep each word under 80 characters and each supplied meaning under 300.');
    return {word,reference_meaning};
  });
  if (new Set(words.map(row=>row.word.toLocaleLowerCase())).size!==words.length) throw new Error('Use each study word only once.');
  return words;
}
function vocabularyAnswers() {
  return studyWords.map((row,i)=>({...row,definition:$(`vocab-definition-${i}`).value.trim(),sentence:$(`vocab-sentence-${i}`).value.trim()}));
}
function vocabularySnapshot() {
  return JSON.stringify({grade:$('grade').value,class_level:$('class_level').value,model:$('model').value,learning_goal:learningGoal(),answers:vocabularyAnswers()});
}
function updateVocabStale() {
  $('vocab-stale').hidden = !vocabResult || vocabularySnapshot() === vocabResultSnapshot;
}
$('build-vocab').addEventListener('click',()=>{
  message('vocab-setup-message','');
  try {
    const words=parseStudyWords($('vocab-words').value);
    studyWords=words; vocabResult=null; vocabResultSnapshot='';
    $('vocab-cards').replaceChildren(); $('vocab-results').hidden=true; message('vocab-message','');
    words.forEach((row,i)=>{
      const card=document.createElement('article');card.className='vocab-answer-card';
      const title=document.createElement('h3'); title.textContent=`${String(i+1).padStart(2,'0')} · ${row.word}`;card.append(title);
      for (const [kind,label,placeholder,limit] of [['definition','In your own words, what does it mean?','Explain the meaning without copying a dictionary.',400],['sentence','Use it in a sentence','Give enough context to show what the word means.',600]]) {
        const input=document.createElement('textarea');input.id=`vocab-${kind}-${i}`;input.rows=2;input.maxLength=limit;input.placeholder=placeholder;
        const inputLabel=document.createElement('label');inputLabel.htmlFor=input.id;inputLabel.textContent=label;
        input.addEventListener('input',updateVocabStale);card.append(inputLabel,input);
      }
      $('vocab-cards').append(card);
    });
    $('vocab-practice').hidden=false; $('replace-vocab-note').hidden=false;
    $('vocab-definition-0').focus();
  } catch(error) {message('vocab-setup-message',error.message);}
});
function renderVocabulary(result) {
  $('vocab-score').textContent=`${result.earned} / ${result.possible} points · ${result.percentage}%`;
  $('vocab-review').textContent=result.review_words.length ? `A little more practice: ${result.review_words.join(', ')}.` : 'You demonstrated every word. Try a new context to make them stick.';
  const container=$('vocab-result-cards');container.replaceChildren();
  for (const row of result.results) {
    const card=document.createElement('article');card.className='vocab-result-card';
    const title=document.createElement('h3');title.textContent=`${row.word} · ${row.points}/4`;card.append(title);
    for (const text of [`Meaning: ${row.meaning_score}/2 · Use in context: ${row.usage_score}/2`,row.feedback,`Meaning to remember: ${row.suggested_definition}`,`In context: ${row.example_sentence}`]) {
      const paragraph=document.createElement('p');paragraph.textContent=text;card.append(paragraph);
    }
    container.append(card);
  }
  $('vocab-grading-note').textContent=result.grading_note;
  $('vocab-results').hidden=false; updateVocabStale();
}
$('grade-vocab').addEventListener('click',async()=>{
  if (busy || !studyWords.length) return;
  message('vocab-message','');
  if (!hasKey()) return message('vocab-message','Enter your Anthropic key in the classroom panel.');
  const answers=vocabularyAnswers();
  if (answers.some(row=>!row.definition || !row.sentence)) return message('vocab-message','Add your definition and an example sentence for every word.');
  const submitted=vocabularySnapshot();
  if (vocabResult && submitted===vocabResultSnapshot) {message('vocab-message','Showing your existing review. Revise an answer to request another check.','info');$('vocab-results').scrollIntoView({behavior:'smooth'});return;}
  const data={provider:'anthropic',model:$('model').value,grade:$('grade').value,class_level:$('class_level').value,learning_goal:learningGoal(),answers};
  setBusy(true,'vocabulary');
  try {
    const result=await request('vocabulary/grade',data);
    if (submitted!==vocabularySnapshot()) {message('vocab-message','Your answers or settings changed while grading. Your edits were kept; check them again.','warning');return;}
    vocabResult=result;vocabResultSnapshot=submitted;renderVocabulary(result);$('vocab-results').scrollIntoView({behavior:'smooth',block:'start'});
  } catch(error) {message('vocab-message',error.message);}
  finally {setBusy(false,'vocabulary');}
});
async function loadSentenceLab(fromWelcome=false) {
  if (sentenceData) return;
  if (sentenceLoad) return sentenceLoad;
  sentenceLoad=(async()=>{
    const response=await fetch('/api/sentence-lab');if(!response.ok) throw new Error('The sentence lab could not load. Refresh to try again.');
    sentenceData=await response.json();
    sentenceFocus=new Set(fromWelcome?['participial','complex']:sentenceData.lessons.map(lesson=>lesson.id));
    $('sentence-reference').replaceChildren();
    for (const lesson of sentenceData.lessons) {
      const title=document.createElement('h3');title.textContent=lesson.label;
      const description=document.createElement('p');description.className='criteria';description.textContent=lesson.description;
      const example=document.createElement('p');example.className='small muted';example.textContent=lesson.example;
      $('sentence-reference').append(title,description,example);
    }
    renderPatternPickers();syncPatternSelection();
  })();
  try {await sentenceLoad;} catch(error) {sentenceLoad=null;throw error;}
}
function renderPatternPickers() {
  for (const id of ['welcome-pattern-choices','sentence-pattern-choices']) {
    const container=$(id);container.replaceChildren();
    for (const [group,title] of [['structures','Sentence structures'],['phrases','Phrase types']]) {
      const fieldset=document.createElement('fieldset');fieldset.className='pattern-group';
      const legend=document.createElement('legend');legend.textContent=title;fieldset.append(legend);
      for (const lesson of sentenceData.lessons.filter(row=>row.group===group)) {
        const label=document.createElement('label');label.className='pattern-choice';label.title=lesson.description;
        const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.dataset.patternId=lesson.id;checkbox.checked=sentenceFocus.has(lesson.id);
        checkbox.addEventListener('change',()=>{if(checkbox.checked)sentenceFocus.add(lesson.id);else sentenceFocus.delete(lesson.id);syncPatternSelection();});
        const text=document.createElement('span');text.textContent=lesson.label;label.append(checkbox,text);fieldset.append(label);
      }
      container.append(fieldset);
    }
  }
}
function syncPatternSelection() {
  if(!sentenceData) return;
  document.querySelectorAll('input[data-pattern-id]').forEach(input=>{input.checked=sentenceFocus.has(input.dataset.patternId);});
  const count=`${sentenceFocus.size} selected`;$('welcome-pattern-count').textContent=count;$('sentence-pattern-count').textContent=count;
  const selected=sentenceData.lessons.filter(lesson=>sentenceFocus.has(lesson.id)),previous=$('sentence-target').value;
  $('sentence-target').replaceChildren(...selected.map(lesson=>{const option=document.createElement('option');option.value=lesson.id;option.textContent=lesson.label;return option;}));
  if(!selected.length){const option=document.createElement('option');option.value='';option.textContent='Choose a pattern above';$('sentence-target').append(option);}
  $('sentence-target').value=sentenceFocus.has(previous)?previous:sentenceFocus.has('participial')?'participial':(selected[0]?.id || '');
  $('sentence-target').disabled=!selected.length;$('review-sentence').disabled=busy || !config || !selected.length;
  updateSentenceTarget();identificationDeck=[];nextIdentification();updateWelcomeFocus();
}
document.querySelectorAll('[data-pattern-preset]').forEach(button=>button.addEventListener('click',()=>{
  if(!sentenceData) return;
  const preset=button.dataset.patternPreset;
  sentenceFocus=new Set(sentenceData.lessons.filter(lesson=>preset==='all' || lesson.group===preset).map(lesson=>lesson.id));
  syncPatternSelection();
}));
function shuffled(items) {
  const result=[...items];for(let i=result.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[result[i],result[j]]=[result[j],result[i]];}return result;
}
function nextIdentification() {
  if (!sentenceData) return;
  const mix=$('identify-category').value;
  const eligible=sentenceData.exercises.filter(row=>sentenceFocus.has(row.target_id) && (mix==='selected' || sentenceData.lessons.find(lesson=>lesson.id===row.target_id).group===mix));
  if(!eligible.length) {
    currentIdentification=null;$('identify-sentence').textContent='Choose at least one matching pattern above to begin.';$('identify-choices').replaceChildren();$('check-identify').disabled=true;$('next-identify').disabled=true;message('identify-feedback','');return;
  }
  if (!identificationDeck.length) identificationDeck=shuffled(eligible);
  currentIdentification=identificationDeck.pop();identificationAnswered=false;
  const group=sentenceData.lessons.find(lesson=>lesson.id===currentIdentification.target_id).group;
  const container=$('identify-sentence');container.replaceChildren();
  const {sentence,highlight}=currentIdentification;
  if (highlight) {
    const index=sentence.indexOf(highlight), mark=document.createElement('mark');mark.textContent=highlight;
    container.append(document.createTextNode(sentence.slice(0,index)),mark,document.createTextNode(sentence.slice(index+highlight.length)));
  } else container.textContent=sentence;
  $('identify-instruction').textContent=group==='phrases' ? 'Name the highlighted phrase. Questions follow your selected patterns; answer choices include other types. Instant checking is free.' : 'Classify the whole sentence by its clauses. Questions follow your selected patterns. Instant checking is free.';
  $('identify-choices').replaceChildren(...shuffled(sentenceData.lessons.filter(lesson=>lesson.group===group)).map(lesson=>{
    const label=document.createElement('label');label.className='identify-choice';
    const input=document.createElement('input');input.type='radio';input.name='identify-answer';input.value=lesson.id;
    const text=document.createElement('span');text.textContent=lesson.label;label.append(input,text);return label;
  }));
  $('check-identify').disabled=false;$('next-identify').disabled=false;message('identify-feedback','');
}
$('identify-category').addEventListener('change',()=>{identificationDeck=[];nextIdentification();});
$('next-identify').addEventListener('click',nextIdentification);
$('check-identify').addEventListener('click',()=>{
  if (!currentIdentification || identificationAnswered) return;
  const selected=document.querySelector('input[name="identify-answer"]:checked');
  if (!selected) return message('identify-feedback','Choose a structure or phrase type first.');
  identificationAnswered=true;identificationTried++;
  document.querySelectorAll('input[name="identify-answer"]').forEach(input=>{input.disabled=true;});
  const correct=selected.value===currentIdentification.target_id;if(correct) identificationCorrect++;
  const lesson=sentenceData.lessons.find(row=>row.id===currentIdentification.target_id);
  message('identify-feedback',`${correct ? 'You’ve got it.' : 'Keep practicing.'} ${lesson.label}: ${currentIdentification.explanation}`,correct?'success':'warning');
  $('identify-progress').textContent=`${identificationCorrect} correct · ${identificationTried} tried`;
  $('check-identify').disabled=true;
});
function sentenceMode(mode) {
  $('identify-panel').hidden=mode!=='identify';$('sentence-write-panel').hidden=mode!=='write';
  for (const [id,active] of [['identify-mode',mode==='identify'],['write-mode',mode==='write']]) {$(id).classList.toggle('selected',active);$(id).setAttribute('aria-pressed',String(active));}
}
$('identify-mode').addEventListener('click',()=>sentenceMode('identify'));
$('write-mode').addEventListener('click',()=>sentenceMode('write'));
function updateSentenceTarget() {
  if (!sentenceData) return;
  const lesson=sentenceData.lessons.find(row=>row.id===$('sentence-target').value);
  if(!lesson){$('sentence-description').textContent='Choose a pattern above to start writing.';$('sentence-example-hint').textContent='';updateSentenceStale();return;}
  $('sentence-description').textContent=lesson.description;$('sentence-example-hint').textContent='Example: '+lesson.example;updateSentenceStale();
}
function sentenceSnapshot() {return JSON.stringify({sentence:$('practice-sentence').value.trim(),target_id:$('sentence-target').value,grade:$('grade').value,model:$('model').value,learning_goal:learningGoal()});}
function updateSentenceStale() {$('sentence-result-stale').hidden=!sentenceReview || sentenceSnapshot()===sentenceReviewSnapshot;}
$('sentence-target').addEventListener('change',updateSentenceTarget);$('practice-sentence').addEventListener('input',updateSentenceStale);
$('review-sentence').addEventListener('click',async()=>{
  if(busy || !sentenceData) return;
  message('sentence-message','');
  if(!hasKey()) return message('sentence-message','Enter your Anthropic key in the classroom panel.');
  if(!$('practice-sentence').value.trim()) return message('sentence-message','Write an original sentence first.');
  const submitted=sentenceSnapshot();
  if(sentenceReview && submitted===sentenceReviewSnapshot) return message('sentence-message','Showing your existing review. Revise the sentence or change the target for another check.','info');
  setBusy(true,'sentence');
  try {
    const result=await request('sentence-lab/review',{provider:'anthropic',model:$('model').value,grade:$('grade').value,class_level:$('class_level').value,learning_goal:learningGoal(),target_id:$('sentence-target').value,sentence:$('practice-sentence').value.trim()});
    if(submitted!==sentenceSnapshot()) return message('sentence-message','Your sentence or settings changed while reviewing. Your edits were kept; check again.','warning');
    sentenceReview=result;sentenceReviewSnapshot=submitted;
    $('sentence-verdict').textContent=`${result.matches_target?'Target demonstrated':'A little more practice'} · ${result.target_label}`;
    $('sentence-explanation').textContent=result.explanation;
    $('sentence-parts').replaceChildren(...result.parts.map(part=>{const item=document.createElement('li');item.textContent=`“${part.text}” — ${part.role}`;return item;}));
    $('sentence-next-step').textContent='Next step: '+result.next_step;$('sentence-revision').textContent='One possible example: '+result.example_revision;
    $('sentence-result').hidden=false;updateSentenceStale();
  } catch(error){message('sentence-message',error.message);} finally{setBusy(false,'sentence');}
});
async function accountRequest(path,data,method='POST') {
  const response=await fetch('/api/account/'+path,{method,headers:{'Content-Type':'application/json'},...(data?{body:JSON.stringify(data)}:{})});
  const result=await response.json();if(!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'Check your account details and try again.');return result;
}
function updateAccount() {
  const user=accountState.user;
  $('account-open').textContent=user ? user.display_name : 'Account';
  $('account-guest').hidden=!!user;$('account-member').hidden=!user;
  $('account-submit').disabled=!accountState.available;
  const providers=accountState.social_providers || [];
  document.querySelectorAll('[data-social-provider]').forEach(button=>{const provider=providers.find(row=>row.id===button.dataset.socialProvider);button.disabled=!accountState.available || !provider?.ready;button.title=provider?.ready?'Sign in securely with '+provider.label:'Not enabled yet';});
  $('social-status').textContent=accountState.available && providers.some(row=>row.ready)?'New here? Continuing creates your account. Use the same sign-in method next time.':'Google, Apple and Microsoft sign-in are awaiting account setup.';
  $('account-storage-note').textContent=accountState.available ? 'An optional account saves your learning goal and recent practice results. Your API key and drafts are never saved.' : 'Accounts are prepared, but a persistent database still needs to be connected. All practice tools work as a guest.';
  if(user) $('account-greeting').textContent='Welcome, '+user.display_name+'.';
}
async function loadAccount(applyProfile=false) {
  try {
    accountState=await accountRequest('me',null,'GET');updateAccount();
    if(applyProfile && accountState.user && config) {
      const user=accountState.user;if(!learningGoal()) $('learning-goal').value=user.learning_goal;
      if(config.grades.includes(user.grade)) {$('grade').value=user.grade;$('welcome-grade').value=user.grade;}
      update();
    }
    if(accountState.user) {
      const history=await accountRequest('history',null,'GET');
      $('account-history').replaceChildren(...history.activities.map(activity=>{const item=document.createElement('li');item.textContent=activity.summary;return item;}));
      if(!history.activities.length) {const item=document.createElement('li');item.textContent='Your next completed review will appear here.';$('account-history').append(item);}
    }
  } catch(error) {message('account-message',error.message);}
}
$('account-open').addEventListener('click',()=>{$('account-dialog').showModal();loadAccount();});
$('account-close').addEventListener('click',()=>{$('account-dialog').close();$('account-password').value='';});
$('account-dialog').addEventListener('close',()=>{$('account-password').value='';});
function accountModeSelect(mode) {
  accountMode=mode;$('display-name-field').hidden=mode!=='signup';$('account-password').autocomplete=mode==='signup'?'new-password':'current-password';$('account-submit').textContent=mode==='signup'?'Create my account':'Sign in';
  for(const [id,active] of [['signup-mode',mode==='signup'],['login-mode',mode==='login']]) {$(id).classList.toggle('selected',active);$(id).setAttribute('aria-pressed',String(active));}
  message('account-message','');
}
$('signup-mode').addEventListener('click',()=>accountModeSelect('signup'));$('login-mode').addEventListener('click',()=>accountModeSelect('login'));
document.querySelectorAll('[data-social-provider]').forEach(button=>button.addEventListener('click',()=>{
  const provider=(accountState.social_providers || []).find(row=>row.id===button.dataset.socialProvider);
  if(!provider?.ready) return;
  if(authPopup && !authPopup.closed) {authPopup.focus();return;}
  message('account-message','');
  authPopup=window.open('/api/account/oauth/'+provider.id+'/start','studio-social-signin','width=520,height=720');
  if(!authPopup) return message('account-message','Allow a sign-in popup for this site, then try again. Your current work is kept.');
  message('account-message','Finish signing in in the new window. Your work stays in this tab.','info');
  clearInterval(authPopupTimer);
  const began=Date.now();
  authPopupTimer=setInterval(()=>{
    if(authPopup?.closed || Date.now()-began>15*60*1000) {clearInterval(authPopupTimer);authPopupTimer=null;loadAccount();}
  },1500);
}));
window.addEventListener('message',async event=>{
  if(event.origin!==location.origin || event.source!==authPopup || event.data?.type!=='studio-auth') return;
  clearInterval(authPopupTimer);authPopupTimer=null;authPopup=null;
  await loadAccount(false);
  if(event.data.status==='success' && accountState.user) {
    const user=accountState.user;
    if(!user.learning_goal) {
      const grade=$('welcome').hidden?$('grade').value:$('welcome-grade').value;
      try {await accountRequest('profile',{learning_goal:learningGoal(),grade},'PATCH');user.learning_goal=learningGoal();user.grade=grade;} catch {}
    } else if(!learningGoal()) {$('learning-goal').value=user.learning_goal;}
    update();
  }
  message('account-message',event.data.status==='success' && accountState.user?'You’re signed in. Your current work is kept.':'Sign-in was cancelled or could not be verified. Please try again.',event.data.status==='success' && accountState.user?'success':'warning');
});
window.addEventListener('focus',()=>{if(authPopup && $('account-dialog').open) loadAccount();});
$('account-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!accountState.available) return;
  $('account-submit').disabled=true;message('account-message','');
  const data={username:$('account-username').value.trim(),password:$('account-password').value};
  if(accountMode==='signup') {data.display_name=$('account-name').value.trim();data.learning_goal=learningGoal();data.grade=$('welcome').hidden?$('grade').value:$('welcome-grade').value;}
  try{await accountRequest(accountMode,data);$('account-password').value='';await loadAccount(true);message('account-message','You’re signed in. Your next completed reviews will be saved.','success');}
  catch(error){message('account-message',error.message);}finally{$('account-submit').disabled=!accountState.available;}
});
$('save-profile').addEventListener('click',async()=>{try{await accountRequest('profile',{learning_goal:learningGoal(),grade:$('grade').value},'PATCH');message('account-message','Your goal and grade are saved.','success');}catch(error){message('account-message',error.message);}});
$('account-logout').addEventListener('click',async()=>{try{await accountRequest('logout',{});accountState.user=null;$('api-key').value='';updateAccount();update();message('account-message','Signed out. Your key is cleared; current practice stays in this tab.','success');}catch(error){message('account-message',error.message);}});
async function initialize() {
  try {
    const response = await fetch('/api/config'); if (!response.ok) throw new Error(); config = await response.json();
    for (const [id, options, selected] of [['grade',config.grades,'Grade 11'],['class_level',config.classes,'On-level / regular']]) {
      $(id).replaceChildren(...options.map(value => {const option = document.createElement('option'); option.value = value; option.textContent = value; return option;}));
      $(id).value = selected; $(id).disabled = false;
    }
    $('model').replaceChildren(...config.models.map(model => {const option = document.createElement('option'); option.value = model.id; option.textContent = model.label; return option;}));
    $('model').disabled = false;
    $('welcome-grade').replaceChildren(...config.grades.map(value => {const option=document.createElement('option');option.value=value;option.textContent=value;return option;}));
    $('welcome-grade').value=$('grade').value; $('welcome-grade').disabled=false;
    $('start-learning').disabled=false;
    $('user-rubric').textContent = config.training_rubric.text;
    $('reference-status').textContent = config.references.amplify_loaded ? 'Your rubric, style comparisons, and Amplify reference excerpts are loaded.' : 'Your rubric and style comparisons are loaded. Amplify references are not loaded yet.';
    $('model').value = config.model; $('core-criteria').textContent = config.core_criteria; setBusy(false,'feedback'); update(); loadAccount(true);
  } catch {message('feedback-message','The classroom settings could not load. Refresh the page to retry.');}
}
route();
initialize();
