import { readFileSync, readdirSync } from 'node:fs';
import { parseSave } from '../docs/js/ess.js';

const SAVES = process.argv[2] ?? 'C:/Program Files (x86)/Steam/steamapps/common/Oblivion/Saves';
const data = JSON.parse(readFileSync(new URL('../docs/data/collectibles.json', import.meta.url), 'utf8'));

for (const f of readdirSync(SAVES).filter(f => f.endsWith('.ess'))) {
  const s = parseSave(readFileSync(`${SAVES}/${f}`));
  const hi = s.plugins.findIndex(p => p.toLowerCase() === 'nehrim.esm') << 24;
  const counts = {};
  const got = [];
  for (const i of data.items) {
    counts[i.kind] ??= [0, 0];
    counts[i.kind][1]++;
    const taken = i.holder ? -s.inventoryChange((hi | i.holder) >>> 0, (hi | i.item) >>> 0) >= i.nth : s.removed.get((hi | i.ref) >>> 0);
    if (taken) { counts[i.kind][0]++; got.push(`${i.id} ${i.area ?? i.near?.name}`); }
  }
  const symbolVar = s.globals.get((hi | data.symbolVar) >>> 0);
  console.log(`${f}\n  ${s.header.name} L${s.header.level} "${s.header.location}" plugins=${s.plugins.join(',')}`);
  console.log(`  ${Object.entries(counts).map(([k, [a, b]]) => `${k} ${a}/${b}`).join('  ')}  NehrimSymbolVar=${symbolVar}`);
  if (got.length) console.log(`  ${got.join(' | ')}`);
  if (symbolVar !== counts.symbol[0]) { console.error('  MISMATCH between symbol counter and disabled symbols'); process.exitCode = 1; }
}
