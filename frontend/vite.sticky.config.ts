import {defineConfig} from 'vite';
export default defineConfig({define:{'process.env.NODE_ENV':'"production"'},build:{outDir:'/tmp/sticky-fixture',emptyOutDir:true,lib:{entry:'tests/projectStickyHarness.jsx',name:'StickyFixture',formats:['iife'],fileName:()=> 'fixture.js',cssFileName:'fixture'}}});
