import test from 'node:test';
import assert from 'node:assert/strict';
import { filterPersonas, personaWords, personaId } from '../src/personaCatalog.ts';

const people = [
  {id:'a',first_name:'Michał',last_name:'Wrona',geo:'PL',country:'Польша',specialization:'Analityk gier',specializations:['RTP']},
  {id:'b',first_name:'Mikkel',last_name:'Sørensen',geo:'DK',country:'Дания',specialization:'Analytiker',specializations:['Mobiloplevelser']},
  {id:'c',first_name:'Eliška',last_name:'Němcová',geo:'CZ',country:'Чехия',specialization:'Redaktorka',specializations:['Bonusy']},
];
test('search handles accented names and combines all search terms', () => {
  assert.deepEqual(filterPersonas(people,'','michal rtp').map(p=>p.id),['a']);
  assert.deepEqual(filterPersonas(people,'','sorensen').map(p=>p.id),['b']);
  assert.deepEqual(filterPersonas(people,'','eliska nemcova').map(p=>p.id),['c']);
});
test('GEO filtering and search work together without losing source records', () => {
  assert.equal(filterPersonas(people,'PL','').length,1);
  assert.equal(filterPersonas(people,'CZ','michal').length,0);
  assert.equal(filterPersonas(people,'','').length,3);
});
test('word count supports biography languages and hyphenated words', () => {
  assert.equal(personaWords('Michał, Amélie a Sørensen. Reader-first player’s guides.'),7);
  assert.equal(personaWords('  \n\n '),0);
});
test('profile paths preserve stable identifiers and reject unrelated routes', () => {
  assert.equal(personaId('/personas/ondrej-vacek/'),'ondrej-vacek');
  assert.equal(personaId('/personas/new/'),'new');
  assert.equal(personaId('/personas'),null);
  assert.equal(personaId('/personas/one/extra'),null);
});
