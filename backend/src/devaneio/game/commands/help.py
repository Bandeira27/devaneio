"""Texto da ajuda do CLI."""

from __future__ import annotations

HELP = """\
Comandos (prefixe com `id:` para escolher o personagem quando houver mais de um):
  olhar                                  onde o grupo está, saídas, quem está aqui
  entrar <id> "<nome>" [FOR=3 ...] [+item ...]  novo personagem; omitidos usam o padrão;
                                         +espada põe a espada no inventário
  ir <local>                             mover o grupo para um local conectado
  testar <habilidade> <dificuldade> [modificador]
  atacar <arma> <alvo> [modificador]     teste da habilidade da arma (precisa estar no inventário); acerto fere
  ferir <alvo> <quantia> ["fonte"]       dano fixo (armadilha, queda...)
  curar <alvo> <quantia> ["fonte"]       cura fixa (poção, magia); levanta quem estava caído
  descansar                              recupera hp do grupo (sem hostis por perto) e gasta o turno
  ficha [id]                             atributos, hp e inventário
  marcos                                 marcos da trama e seus estados
  marco ativar|concluir|falhar <id>      mover um marco à mão (o diretor cuida dos gatilhos)
  fatos                                  fatos da campanha, revelados e ocultos
  revelar <id>                           tornar um fato público (o diretor revela os que têm gatilho)
  log [n]                                últimos eventos (padrão 10)
  fim                                    encerrar o turno: o diretor age, NPCs hostis reagem
  ajuda                                  esta lista
  sair                                   fechar (a partida já está salva)"""
