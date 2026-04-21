// Canonical address normalization — mirrors trashalert-web's
// src/lib/normalize-address.ts. Import scripts should run raw source rows
// through `normalizeForImport()` before upserting into schedule_reports so
// stored addresses match what the web app's /api/schedule resolver looks up.
//
// If you change rules here, mirror the change in the TS module and
// re-verify coverage with scripts/verify-coverage.mjs.

const SUFFIX_GROUPS = [
  ['st', 'street'],
  ['ave', 'avenue', 'av'],
  ['blvd', 'boulevard', 'bl'],
  ['rd', 'road'],
  ['dr', 'drive'],
  ['ln', 'lane'],
  ['pl', 'place'],
  ['ct', 'court'],
  ['hwy', 'highway', 'hway'],
  ['pkwy', 'parkway', 'pky'],
  ['cir', 'circle'],
  ['ter', 'terrace'],
  ['way', 'wy'],
  ['trl', 'trail'],
  ['sq', 'square'],
  ['xing', 'crossing'],
  ['plz', 'plaza'],
]

const STREET_SUFFIX_TO_CANONICAL = Object.fromEntries(
  SUFFIX_GROUPS.flatMap((group) => group.map((variant) => [variant, group[0]]))
)

const DIRECTIONAL = {
  north: 'n', n: 'n',
  south: 's', s: 's',
  east: 'e', e: 'e',
  west: 'w', w: 'w',
  northeast: 'ne', ne: 'ne',
  northwest: 'nw', nw: 'nw',
  southeast: 'se', se: 'se',
  southwest: 'sw', sw: 'sw',
}

const ORDINALS = {
  first: '1st', second: '2nd', third: '3rd', fourth: '4th',
  fifth: '5th', sixth: '6th', seventh: '7th', eighth: '8th',
  ninth: '9th', tenth: '10th', eleventh: '11th', twelfth: '12th',
}

export function normalizeCity(city) {
  let s = String(city || '').toLowerCase().trim().replace(/[.,]/g, '')
  s = s.replace(/\s+/g, '-').replace(/-+/g, '-')
  s = s.replace(/-(tx|ca|ny|nj|fl|il|oh|pa|ga|nc|mi|az|ma|co|wa|or|va|md|wi|mo|in|tn|ct|mn|sc|la|ok|ky|nv|al|ut|ar|ms|ks|nm|ne|ia|id|mt|wy|nd|sd|de|me|nh|vt|ri|wv|hi|ak|dc)$/i, '')
  return s
}

export function normalizeAddressGeneric(input) {
  let s = String(input || '').toLowerCase().trim()

  s = s.replace(/,\s*[a-z .'-]+,\s*[a-z][a-z]\s+\d{5}(-\d{4})?\s*$/i, '')
  s = s.replace(/,\s*[a-z][a-z]\s+\d{5}(-\d{4})?\s*$/i, '')
  s = s.replace(/,\s*[a-z][a-z]\s*$/i, '')
  s = s.replace(/,\s*[a-z .'-]+\s*$/i, '')
  s = s.replace(/\s+\d{5}(-\d{4})?\s*$/i, '')

  s = s.replace(/\s+(apt|unit|ste|suite|#|bldg|building|fl|floor|rm|room)\s*\S*$/i, '')

  s = s.replace(/[.,]/g, ' ')
  s = s.replace(/[^a-z0-9#\- ]/g, ' ')
  s = s.replace(/\s+/g, ' ').trim()

  const tokens = s.split(' ')
  const out = []
  for (const t of tokens) {
    if (DIRECTIONAL[t]) out.push(DIRECTIONAL[t])
    else if (STREET_SUFFIX_TO_CANONICAL[t]) out.push(STREET_SUFFIX_TO_CANONICAL[t])
    else if (ORDINALS[t]) out.push(ORDINALS[t])
    else out.push(t)
  }

  if (out.length > 0 && /^\d+$/.test(out[0])) {
    out[0] = out[0].replace(/^0+(?=\d)/, '')
  }

  return out.join(' ').trim()
}

// Default entry point for import scripts — run row.address and row.city through
// this before upsert so writes match the lookup path.
export function normalizeForImport(address, city) {
  return {
    address: normalizeAddressGeneric(address),
    city: normalizeCity(city),
  }
}
