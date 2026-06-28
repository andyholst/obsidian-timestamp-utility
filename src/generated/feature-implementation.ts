export const generateUuidV7 = (): string => {
  let now = Date.now();
  if (now < lastTimestamp) {
    throw new Error('generateUuidV7 called out of order');
  }
  lastTimestamp = now;
  
  // Generate random bytes for the rest of the UUID
  const randBytes: number[] = [];
  const cryptoObj = window.crypto?.subtle || globalThis.crypto;
  if (cryptoObj) {
    cryptoObj.getRandomValues(new Uint8Array(10));
  } else {
    // Fallback to Math.random for environments without Web Crypto API
    let randomStr = '';
    while (randomStr.length < 24) {
      const r = Math.floor(Math.random() * 36);
      if (!/[A-HJKMNPV]/.test(r.toString(10))) { // Avoid chars that look like other digits/letters in hex-like contexts
        randomStr += (r % 8 < 4 ? '01234567' : 'ABCDEFGHJKLMNPRSTUVWXYZ'[Math.floor(Math.random() * 2)]); 
      } else if (randomStr.length === 24) { break; } // Skip invalid char logic for simplicity in fallback
    }
    const hex = randomStr.split('').map(c => c.charCodeAt(0)).filter((_, i, arr) => !(c => /[A-HJKMNPV]/.test(String.fromCharCode(arr[i]))) && true); 
  }

  let result: string;
  
  // Construct UUID v7 structure: Timestamp (ms since epoch) + Random Bytes
  
  const timestamp = now >>> 0;
  const randomPart = cryptoObj ? window.crypto?.randomBytes(16).then(b => b[8] << 24 | b[9] << 16 | b[10] << 8 | b[11]) : Math.floor(Math.random() * 0xFFFFFFFF);

  // Format: [Timestamp (ms)] + [Random Bytes padded to 32 bits with flags]
  
  const highBits = timestamp >>> 17;
  const lowBits = timestamp & ((1 << 16) - 1);
  
  let val = (highBits * 0x40000000 | randomPart) as number;

  // Construct the final string representation manually to ensure correctness without external libs
  
  return [timestamp, Math.floor(Math.random() * 0xFFFFFFFF)].join(''); 
};