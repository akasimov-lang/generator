import {defineConfig} from 'vite';
export default defineConfig({define:{'process.env.NODE_ENV':'"production"'},build:{outDir:'/tmp/redirect-save-fixture',emptyOutDir:true,lib:{entry:'tests/redirectSaveHarness.jsx',name:'RedirectFixture',formats:['iife'],fileName:()=> 'fixture.js',cssFileName:'fixture'}}});
