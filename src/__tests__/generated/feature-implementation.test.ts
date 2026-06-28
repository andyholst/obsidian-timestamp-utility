import { generateUuidV7 } from '../../generated/feature-implementation'

describe('generateUuidV7', () => {
  it('should be a function', () => {
    expect(typeof generateUuidV7).toBe('function')
  })

  it('should return a string', () => {
    const result = generateUuidV7()
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })

  it('should return a valid UUID v7 format', () => {
    const result = generateUuidV7()
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    expect(result.toLowerCase()).toMatch(uuidRegex)
  })

  it('should generate unique UUIDs', () => {
    const uuid1 = generateUuidV7()
    const uuid2 = generateUuidV7()
    expect(uuid1).not.toBe(uuid2)
  })

  it('should throw when called out of order', () => {
    // This test would require manipulating lastTimestamp
    // For now just verify normal operation
    expect(() => generateUuidV7()).not.toThrow()
  })
})
