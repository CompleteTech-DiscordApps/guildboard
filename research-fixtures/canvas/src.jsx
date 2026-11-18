import React from 'react';
import {preserveElementIds} from './preserve-ids.mjs';
import {recordSceneChange} from './record-change.mjs';
import {createRoot} from 'react-dom/client';
import {CaptureUpdateAction, Excalidraw, convertToExcalidrawElements, loadFromBlob, serializeAsJSON} from '@excalidraw/excalidraw';
import '@excalidraw/excalidraw/index.css';
window.EXCALIDRAW_ASSET_PATH = '/node_modules/@excalidraw/excalidraw/dist/prod/';
window.events = [];
window.makeElements = elements => preserveElementIds(convertToExcalidrawElements, elements);
window.capture = CaptureUpdateAction;
window.assetSerialization = {loadFromBlob, serializeAsJSON};

function handleSceneChange(elements, state, files) {
  recordSceneChange(window.events, elements, state, files);
  window.observeFixtureChange?.(elements);
}

function Fixture() {
  const [readonly, setReadonly] = React.useState(false);
  window.setReadonly = setReadonly;
  return <Excalidraw
    excalidrawAPI={api => { window.editor = api; }}
    viewModeEnabled={readonly}
    onChange={handleSceneChange}
  />;
}
createRoot(document.getElementById('root')).render(<Fixture/>);
