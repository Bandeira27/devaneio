/** O tempo de jogo como a tela o mostra: o relógio visual, a frase para o leitor de tela e a conta do que já passou. */

/** O tempo no relógio, `h:mm:ss` (as horas sem teto: uma campanha longa passa de 24 h). */
export function clockText(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  return `${hours}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
}

/** O tempo em palavras, só até os minutos ("1 hora e 23 minutos"): o leitor de tela não anuncia segundo a segundo. */
export function spokenTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const h = hours === 1 ? '1 hora' : `${hours} horas`;
  const m = minutes === 1 ? '1 minuto' : `${minutes} minutos`;
  if (hours === 0) {
    return minutes === 0 ? 'menos de um minuto' : m;
  }
  return minutes === 0 ? h : `${h} e ${m}`;
}

/** O que o relógio de jogo marca agora: o valor do servidor mais o tempo desde que ele chegou, só enquanto roda. */
export function currentSeconds(
  clock: { seconds: number; running: boolean; receivedAt: number },
  now: number,
): number {
  if (!clock.running || clock.receivedAt === 0) {
    return clock.seconds;
  }
  return clock.seconds + Math.max(0, Math.floor((now - clock.receivedAt) / 1000));
}
