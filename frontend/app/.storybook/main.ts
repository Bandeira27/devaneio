import type { StorybookConfig } from '@storybook/angular-vite';

const config: StorybookConfig = {
  framework: '@storybook/angular-vite',
  stories: ['../src/**/*.stories.ts'],
  addons: ['@storybook/addon-a11y'],
  core: { disableTelemetry: true }, // o projeto é local-first: nada sai da máquina sem o dono pedir
};

export default config;
