// Global jest type declarations to avoid needing @types/jest installed
declare const expect: any
declare const test: any
declare const jest: any
declare const describe: any
declare const it: any
declare const beforeEach: any
declare const afterEach: any
declare const beforeAll: any
declare const afterAll: any
declare const require: any

declare namespace jest {
  interface Mock<T = any> extends Function {
    new (...args: any[]): T
    (...args: any[]): T
    mockReturnValue(val: any): T
    mockResolvedValue(val: Promise<any>): T
    mock: any
  }
  interface Fn<T = any> extends Function {
    new (...args: any[]): T
    (...args: any[]): T
    mockReturnValue(val: any): T
    mockResolvedValue(val: Promise<any>): T
    mock: any
  }
}
