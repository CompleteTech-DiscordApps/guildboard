async (page) => {
  const checks = [];
  function check(name, condition, details = null) {
    checks.push({name, result:condition?'pass':'fail', details});
    if(!condition) throw Error(name + ' failed: ' + JSON.stringify(details));
  }
  const state = () => page.evaluate(()=>window.fixtureState());
  await page.evaluate(()=>{document.body.tabIndex=-1;document.body.focus();});
  await page.keyboard.press('Tab');
  check('keyboard skip link is first focus stop', await page.locator('.skip').evaluate(e=>e===document.activeElement));
  await page.keyboard.press('Enter');
  check('skip link moves focus to object heading', await page.locator('#objects').evaluate(e=>e===document.activeElement));
  await page.locator('#help').focus(); await page.keyboard.press('Enter');
  check('dialog moves focus inside', await page.locator('#close-guide').evaluate(e=>e===document.activeElement));
  await page.keyboard.press('Tab');
  check('dialog keeps Tab inside', await page.locator('#close-guide').evaluate(e=>e===document.activeElement));
  await page.keyboard.press('Escape');
  check('Escape closes dialog and restores trigger focus',
    await page.locator('#help').evaluate(e=>e===document.activeElement)&&!(await page.locator('#guide').evaluate(e=>e.open)));

  await page.locator('[data-object="note-b"]').click();
  check('named object selection focuses labeled text field', await page.getByLabel('Object text',{exact:true}).evaluate(e=>e===document.activeElement));
  await page.getByLabel('Object text',{exact:true}).fill('Accessible next action');
  await page.getByLabel('Horizontal position',{exact:true}).fill('123');
  await page.keyboard.press('Tab'); await page.keyboard.press('Tab'); await page.keyboard.press('Enter');
  let current=await state();
  check('keyboard queues change without accepting content', current.pending?.text==='Accessible next action'&&current.revision===0&&current.accepted[1].text==='Write the first action.');
  check('pending status is semantic and does not steal focus',
    await page.locator('#status').getAttribute('role')==='status'&&await page.locator('#status').getAttribute('aria-live')==='polite'&&await page.locator('#queue').evaluate(e=>e===document.activeElement));
  await page.evaluate(()=>document.querySelector('#revoke').click()); current=await state();
  check('asynchronous revoke moves focus to permission explanation',
    await page.locator('#permission').evaluate(e=>e===document.activeElement)&&await page.locator('#queue').isDisabled());
  check('revoke preserves pending draft and blocks local acceptance', current.revision===0&&current.pending?.text==='Accessible next action'&&await page.locator('#accept').isDisabled()&&await page.locator('#object-text').evaluate(e=>e.readOnly));
  await page.locator('#disconnect').click(); await page.locator('#reconnect').click(); current=await state();
  check('reconnect does not optimistically restore writer', current.connected&&!current.verified&&await page.locator('#queue').isDisabled()&&current.pending!==null);
  await page.locator('#reject').click(); await page.locator('#verify').click();
  check('rejection leaves accepted content unchanged and draft available', (await state()).revision===0&&await page.locator('#object-text').inputValue()==='Accessible next action');
  await page.locator('#queue').click(); await page.locator('#accept').click(); current=await state();
  check('explicit fixture receipt alone promotes queued text and position', current.revision===1&&current.accepted[1].text==='Accessible next action'&&current.accepted[1].x===123&&current.pending===null);
  await page.locator('#object-x').fill('1001'); await page.locator('#queue').click();
  check('invalid coordinate has an error and no accepted effect', (await state()).revision===1&&(await page.locator('#error').textContent()).includes('0 to 1000'));

  const viewports=[];
  for(const [width,height] of [[320,640],[360,640],[390,844],[768,1024],[1024,768],[1280,720],[320,256],[568,320]]) {
    await page.setViewportSize({width,height});
    const metrics=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
      minimumControlWidth:Math.min(...[...document.querySelectorAll('button,input,textarea')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.getBoundingClientRect().width)),
      minimumControlHeight:Math.min(...[...document.querySelectorAll('button,input,textarea')].filter(e=>e.getBoundingClientRect().height>0).map(e=>e.getBoundingClientRect().height))}));
    check(`synthetic viewport ${width}x${height} reflows controls`,metrics.scrollWidth<=width+1&&metrics.minimumControlHeight>=44&&metrics.minimumControlWidth>=44,metrics);
    viewports.push({width,height,...metrics});
  }
  await page.emulateMedia({reducedMotion:'reduce',forcedColors:'active'});
  check('reduced-motion and forced-colors CSS branches available in emulation',await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches&&matchMedia('(forced-colors: active)').matches));
  await page.emulateMedia({reducedMotion:'no-preference',forcedColors:'none'});
  await page.setViewportSize({width:1280,height:900});
  const selectionBaseline=await state();
  const selectionStatus=await page.locator('#status').textContent();
  const invalidFields={text:'Accessible next action',x:'1001',y:'160'};
  async function selectionPhase(selected, fields, focus) {
    const observed=await page.evaluate(()=>({
      selected:[...document.querySelectorAll('[data-object][aria-current="true"]')].map(e=>e.dataset.object),
      fields:{text:document.querySelector('#object-text').value,x:document.querySelector('#object-x').value,y:document.querySelector('#object-y').value},
      focus:document.activeElement.id,
      formValid:document.querySelector('#editor').checkValidity(),
      alert:document.querySelector('#error').textContent,
      status:document.querySelector('#status').textContent
    }));
    const snapshot=await state();
    return {...observed,
      selectionMatches:JSON.stringify(observed.selected)===JSON.stringify([selected]),
      fieldsMatch:JSON.stringify(observed.fields)===JSON.stringify(fields),
      focusMatches:observed.focus===focus,
      acceptedUnchanged:JSON.stringify(snapshot.accepted)===JSON.stringify(selectionBaseline.accepted),
      revisionUnchanged:snapshot.revision===selectionBaseline.revision,
      pendingUnchanged:JSON.stringify(snapshot.pending)===JSON.stringify(selectionBaseline.pending),
      statusUnchanged:observed.status===selectionStatus};
  }
  const phases={};
  phases.initialInvalidDraft=await selectionPhase('note-b',invalidFields,'object-x');
  await page.locator('[data-object="note-a"]').focus(); await page.keyboard.press('Enter');
  const validObject=selectionBaseline.accepted.find(object=>object.id==='note-a');
  phases.validSelection=await selectionPhase('note-a',
    {text:validObject.text,x:String(validObject.x),y:String(validObject.y)},'object-text');
  phases.validSelection.clearsUnrelatedStaleAlert=phases.validSelection.alert==='';
  await page.locator('[data-object="note-b"]').focus(); await page.keyboard.press('Enter');
  phases.returnedInvalidDraft=await selectionPhase('note-b',invalidFields,'object-text');
  await page.locator('#object-x').fill('123');
  phases.correctedDraft=await selectionPhase('note-b',{...invalidFields,x:'123'},'object-x');
  phases.correctedDraft.clearsAlert=phases.correctedDraft.alert==='';
  phases.correctedDraft.notQueuedOrAccepted=phases.correctedDraft.status.includes('not queued or accepted');
  check('correcting input clears stale error without claiming acceptance',
    Object.values(phases).every(phase=>phase.selectionMatches&&phase.fieldsMatch&&phase.focusMatches&&
      phase.acceptedUnchanged&&phase.revisionUnchanged&&phase.pendingUnchanged&&phase.statusUnchanged)&&
    !phases.initialInvalidDraft.formValid&&phases.initialInvalidDraft.alert.includes('0 to 1000')&&
    phases.validSelection.formValid&&phases.validSelection.clearsUnrelatedStaleAlert&&
    !phases.returnedInvalidDraft.formValid&&phases.correctedDraft.formValid&&
    phases.correctedDraft.clearsAlert&&phases.correctedDraft.notQueuedOrAccepted,phases);
  await page.screenshot({path:'/tmp/guildboard-t7-fixture.png',fullPage:true});
  return {result:'pass',evidence_kind:'local-headless-browser-fixture-only',browser:page.context().browser().version(),
    checks,viewports,limitations:['No real Discord iframe/client','No screen reader or human review','No Excalidraw integration','Local state simulations, no server authorization/durability','Viewport/input emulation is not hardware acceptance']};
}
