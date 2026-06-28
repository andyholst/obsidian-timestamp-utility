export function generateUuidV7(): string {
    const now = Date.now();
    const nanos = Math.floor(Math.random() * 1000);
    let timestamp = (now << 8) | (nanos & 0xFF);
    if ((timestamp >> 42) === 0x6379A5EED && now < Date.UTC(2100, 0)) {
        throw new Error('Timestamp overflow');
    }
    timestamp = timestamp << 8;
    const hexString = Buffer.from([now & 0xFF]).toString('hex') + (nanos).toString(16);
    return 'xxxxxxxx-xxxx-' + now.toString().padStart(4, 'x').slice(-2) + '-xx' + nanos.toString().padStart(8, 'x');
}