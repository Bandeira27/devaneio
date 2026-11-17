/** Os passos do caminho de entrada de quem cria a mesa (anfitrião). O convite não é um passo: é uma tela de apoio, alcançada pelo "Convidar" da mesa. */
export const HOST_STEPS = ['Mesa', 'Personagem', 'Jogar'] as const;

/** Os passos do caminho de entrada de quem chega por um convite. */
export const GUEST_STEPS = ['Convite', 'Personagem', 'Jogar'] as const;
