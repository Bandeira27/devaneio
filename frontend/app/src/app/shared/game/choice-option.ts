/** Uma opção de escolha única (alvo, arma, dificuldade...): o valor que volta, o rótulo e uma linha de apoio. */
export interface ChoiceOption {
  value: string;
  label: string;
  /** Uma linha de apoio (dano, pontos de vida, fórmula já traduzida). */
  detail?: string;
}
