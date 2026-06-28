export function implementTimestampBasedUuidGen(): string {
    const now = Date.now(); 
    
    // Generate random bytes for sequence number and remaining randomness using Web Crypto API if available
    let buffer: Uint8Array;
    try {
        if ('crypto' in globalThis && 'randomFillSync' in crypto) {
            buffer = new Uint8Array(16);
            (globalThis as any).crypto.getRandomValues(buffer);
        } else {
            // Fallback for environments without secure random
            const fallbackRandom = () => Math.random() * 256;
            buffer = Array.from({ length: 16 }, fallbackRandom) as unknown as Uint8Array;
        }
    } catch (e) {
        if (!buffer && 'crypto' in globalThis && 'randomFillSync' in crypto) {
             let  rndBuf = new Uint8Array(16);
            (globalThis as any).crypto.getRandomValues(rndBuf);
            buffer = rndBuf;
        } else {
            // Ultimate fallback: use random bits for sequence and padding, ensuring function returns something valid.
            // We will construct a specific byte array manually to ensure structure compliance even without crypto randomness quality check in catch block logic below if needed.
             const seqBits = Math.floor(Math.random() * 0x10000); 
             buffer = new Uint8Array(2).map((_, i) => (seqBits >> ((i + 1) * 4)) & 0xff); // Just padding, logic below handles it
        }
    }

    let uuidBytes: number[] = [];

    if (!buffer || buffer.length === 0 && !('crypto' in globalThis)) {
         const rndBuf = new Uint8Array(16);
            (globalThis as any).getRandomValues ? ((globalThis as any).getRandomValues(rndBuf) : null) 
             // Note: getRandomValues is not available on window without crypto import sometimes, so fallback to Math.random if needed.
    }

    let hexString = "";

    try {
        const randomBytes = new Uint8Array(16);
        
        // Attempt secure random generation again safely for the actual buffer used in construction
        if ('crypto' in globalThis && 'randomFillSync' in crypto) {
            (globalThis as any).crypto.getRandomValues(randomBytes);
            
            let bytes: number[] = [];

            const nowMs = BigInt(Date.now()); 
            // UUID v7 Layout (Big Endian interpretation for the string generation):
            // Bits 127-96 : Time Low (32 bits) -> Wait, standard V7 puts timestamp in first field?
            // RFC Draft: "The most significant byte of the time_low is placed at bit position 0." 
            // Actually, let's strictly follow the requirement to set Version and Variant.

            const ts = BigInt(Date.now()); 
            
            // Constructing bytes based on standard UUID v7 layout (RFC draft):
            // Bytes 0-5: Timestamp (48 bits). Wait, timestamp is usually split? 
            // Let's use a robust bit-masking strategy that aligns with the hex output requirements.
            
            let tLo = Number(ts) & 0xFFFFFFFF;       // Lower 32 bits of timestamp value
            let tHi = Number((ts >> BigInt(32)) & BigInt(0xFFFF));   // Upper