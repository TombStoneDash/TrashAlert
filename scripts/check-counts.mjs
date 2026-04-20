#!/usr/bin/env node
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY)

const { data: a } = await supabase.from('schedule_reports').select('city,address,hauler').ilike('city', 'portland%').limit(10)
console.log(`portland% prefix rows: ${a?.length || 0}`)
for (const r of a || []) console.log(`  ${r.city} | ${r.address} | ${r.hauler}`)

const { data: b } = await supabase.from('schedule_reports').select('city,address,hauler').eq('city', 'portland-me').limit(3)
console.log(`\nportland-me explicit: ${b?.length || 0}`)
for (const r of b || []) console.log(`  ${r.address} | ${r.hauler}`)

const { data: c } = await supabase.from('schedule_reports').select('city,address,hauler').eq('city', 'portland-or').limit(3)
console.log(`\nportland-or explicit: ${c?.length || 0}`)
for (const r of c || []) console.log(`  ${r.address} | ${r.hauler}`)
