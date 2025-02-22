import typescript from '@rollup/plugin-typescript';
import { nodeResolve } from '@rollup/plugin-node-resolve';
import terser from '@rollup/plugin-terser';

export default {
    input: 'src/main.ts',
    output: {
        file: 'dist/main.js',
        format: 'cjs',
        sourcemap: false,
    },
    plugins: [
        typescript(),
        nodeResolve(),
        terser({
            compress: {
                drop_console: false,
                passes: 3,
            },
            mangle: true,
            output: {
                comments: false,
            },
        }),
    ],
    external: ['obsidian']
};
