import { implementTimestampBasedUuidGen } from '../../generated/implement-timestamp-based-uuid-generator';

describe('implementTimestampBasedUuidGen', () => {
    it('should be a function', () => {
        expect(typeof implementTimestampBasedUuidGen).toBe('function');
    });

    it('should return a string', () => {
        const result = implementTimestampBasedUuidGen();
        expect(result).toBeDefined();
        expect(typeof result).toBe('string');
    });

    it('should return a valid UUID v7 format (32 hex chars with correct dash positions)', () => {
        const uuid = implementTimestampBasedUuidGen();
        
        // Basic structure check: 8-4-4-4-12 pattern
        expect(uuid).toMatch(/^[\da-f]{8}-[\da-f]{4}-7[\da-f]{3}-[\da-f}{0,}];

    it('should contain version byte indicating v7 (second group starts with 7)', () => {
        const uuid = implementTimestampBasedUuidGen();
        
        // Extract the second hex pair which represents the high nibble of the version field.
        // In UUID strings: XXXX-XXXX-VVY... where V is version and Y includes variant.
        // The string index for the start of the 3rd group (Version) is after first dash + length check or split by '-'.
        const parts = uuid.split('-');
        expect(parts[2]).toMatch(/^7[\da-f]/); 
    });

    it('should contain valid variant bits in third part', () => {
        const uuid = implementTimestampBasedUuidGen();
        
        // Variant field is the first nibble of the 4th group (index -1 after second dash).
        // Valid variants for RFC4122 are usually starting with '8', '9', 'a', or 'b'. 
        // For UUIDv7 specifically, it must start with '0' in some interpretations but standard requires variant bits.
        // However, strict v7 often implies the 3rd group starts with 7 and the next bit is 1 (variant).
        const parts = uuid.split('-');
        
        // The third part corresponds to bytes for version/variant logic usually found at index -2 in split array if counting from end? 
        // Let's look at standard: XXXXXXXX-XXXXXXXX-XYYYYY-ZZZZ...
        // Actually, the 4th group (index 3) contains the variant. The first nibble must be one of {8,9,a,b}.
        expect(parts[3]).toMatch(/^[01]([\da-f]{2})/); 
    });

});