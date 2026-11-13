import assert from 'node:assert/strict';
import test from 'node:test';
import {preserveElementIds} from './preserve-ids.mjs';

test('fixture always explicitly disables converter ID regeneration', () => {
  const input=Object.freeze([{id:'remote-baseline',type:'rectangle'}]);
  const result=Object.freeze([{id:'remote-baseline',type:'rectangle',version:1}]);
  let calls=0;
  const actual=preserveElementIds((received,options)=>{
    calls++;
    assert.equal(received,input);
    assert.deepEqual(options,{regenerateIds:false});
    return result;
  },input);
  assert.equal(calls,1);
  assert.equal(actual,result);
});
