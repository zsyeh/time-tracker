import{expect,it}from'vitest'
import {readFileSync} from 'node:fs'
const tokens=readFileSync(new URL('./tokens.css',import.meta.url),'utf8')
it('uses one neutral surface map independently from accent choices',()=>{
 const definitions=[...tokens.matchAll(/--surface-[a-z-]+:\s*([^;]+);/g)].map(m=>m[1])
 expect(definitions.length).toBeGreaterThan(10)
 for(const value of definitions){expect(value).not.toContain('accent');expect(value).not.toContain('status');expect(value.trim()).toMatch(/^var\(--n-/)}
 expect(tokens).not.toContain('linear-gradient');expect(tokens).not.toContain('radial-gradient')
})
