/** Session flag so /chat only plays the blur entrance once. */
let entered = false

export function hasChatEntered(): boolean {
  return entered
}

export function markChatEntered(): void {
  entered = true
}
