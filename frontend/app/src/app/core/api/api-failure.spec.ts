import { HttpErrorResponse } from '@angular/common/http';
import { ApiFailure } from './api-failure';

function response(status: number, error: unknown): HttpErrorResponse {
  return new HttpErrorResponse({ status, error });
}

describe('ApiFailure', () => {
  it('lê o código e a mensagem do corpo de erro do servidor', () => {
    const failure = ApiFailure.from(
      response(409, { error: { code: 'stale_revision', message: 'a mesa mudou' } }),
    );
    expect(failure).toBeInstanceOf(ApiFailure);
    expect(failure.status).toBe(409);
    expect(failure.code).toBe('stale_revision');
    expect(failure.message).toBe('a mesa mudou');
  });

  it('trata falha de rede (status 0) como o código network', () => {
    const failure = ApiFailure.from(response(0, new ProgressEvent('error')));
    expect(failure.code).toBe('network');
    expect(failure.retryable).toBe(true);
    expect(failure.message).toBe('Sem conexão com o servidor.');
  });

  it.each([
    ['corpo vazio', null],
    ['texto', '<html>502</html>'],
    ['objeto sem error', { detail: 'x' }],
    ['error sem code', { error: { message: 'x' } }],
    ['code que não é texto', { error: { code: 1, message: 'x' } }],
    ['error nulo', { error: null }],
  ])('não confia em corpo fora do formato (%s)', (_name, body) => {
    const failure = ApiFailure.from(response(500, body));
    expect(failure.code).toBe('unknown');
    expect(failure.message).toBe('O servidor respondeu algo inesperado.');
    expect(failure.status).toBe(500);
  });

  it.each([
    [0, true],
    [408, true],
    [429, true],
    [500, true],
    [502, true],
    [400, false],
    [401, false],
    [403, false],
    [404, false],
    [409, false],
    [422, false],
  ])('status %i é repetível: %s', (status, retryable) => {
    expect(new ApiFailure(status, 'x', 'm').retryable).toBe(retryable);
  });
});
