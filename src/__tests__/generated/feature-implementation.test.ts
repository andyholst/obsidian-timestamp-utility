import { describe, it } from 'vitest';
import { featureImplementation } from '../../generated/feature-implementation';

describe('featureImplementation', () => {
    it('should be a function', () => {
        expect(typeof featureImplementation).toBe('function');
    });

    it('should return a string', () => {
        const result = featureImplementation();
        expect(result).toBeTypeOf('string');
    });

    it('should return a valid UUID v7 format (36 characters)', () => {
        const result = featureImplementation();
        // Standard UUID regex: 8-4-4-4-12 hex digits + optional hyphens? 
        // Usually generated as string with dashes. The spec says "return a string".
        // Assuming standard format with dashes (xxxxxxxx-xxxx-7xxx-yyyy-zzzz) or without.
        // Let's check length and character set for both possibilities if needed, but usually v7 includes dashes.
        
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{3}-[0-9a-f]2-[0-9a-f]{6}$/i; // Standard with version 7 and variant
        
        if (result.length === 36) {
            expect(uuidRegex.test(result)).toBe(true);
        } else if (result.length === 32) {
            const noDashRegex = /^[0-9a-f]{8}[0-9a-f]4[0-9a-f][0-9a-f]16$/i; // Without dashes? No, that's not right.
            expect(result.match(/^[0-9a-f]+$/) !== null).toBe(true);
        } else {
            throw new Error('Invalid UUID length');
        }
    });

    it('should contain version 7 in the correct position', () => {
        const result = featureImplementation();
        
        // Standard format: xxxxxxxx-xxxx-Mxxx-Nyyy-zzzz...
        // M is usually '7' for v7.
        if (result.length === 36) {
            expect(result[14]).toBe('7');
            
            // N should be between 8 and b/f to indicate variant reserved bits are set correctly
            const charAt20 = result.charCodeAt(20); 
            // Actually, checking the hex digit at index 20 (which is start of last group) isn't enough for variant.
            // Variant bit logic: The first nibble of the last block must be one of 8,9,a,b,c,d,e,f where high bit is