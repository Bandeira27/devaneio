/** Os passos do caminho de entrada de quem cria a mesa (anfitrião). O convite mora na sala, o último passo. */
export const HOST_STEPS = ['Mesa', 'Personagem', 'Sala'] as const;

/** Os passos do caminho de entrada de quem chega por um convite. */
export const GUEST_STEPS = ['Convite', 'Personagem', 'Sala'] as const;

/** Em que passo cada tela do caminho de entrada está: toda tela do caminho mostra o seu, e só a sala é o último. */
export const ENTRY_STEP = { start: 0, character: 1, lobby: 2 } as const;
