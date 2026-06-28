let lastTimestamp = 0

export const generateUuidV7 = (): string => {
  const now = Date.now()
  if (now < lastTimestamp) {
    throw new Error('generateUuidV7 called out of order')
  }
  lastTimestamp = now

  // Get random bytes using Web Crypto API
  const randomBytes = new Uint8Array(10)
  crypto.getRandomValues(randomBytes)

  // Build UUID v7: timestamp (48 bits) + version (4 bits) + random (76 bits) + variant (2 bits)
  const timestamp = BigInt(now)
  const hex = timestamp.toString(16).padStart(12, '0')

  // Convert random bytes to hex
  const randHex = Array.from(randomBytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')

  // Set version (7) and variant bits
  const versionNibble = '7'
  const variantBits = '8' // variant 10xx

  // Format: xxxxxxxx-xxxx-7xxx-[89ab]xxx-xxxxxxxxxxxx
  return (
    hex.slice(0, 8) +
    '-' +
    hex.slice(8, 12) +
    '-' +
    versionNibble +
    randHex.slice(0, 3) +
    '-' +
    variantBits +
    randHex.slice(3, 6) +
    '-' +
    randHex.slice(6, 18)
  )
}
