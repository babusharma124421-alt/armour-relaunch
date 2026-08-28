import { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.theapp.scamdetect',
  appName: 'the app',
  webDir: 'dist',
  server: {
    url: process.env.VITE_BACKEND_HTTP_URL ?? 'http://localhost:8000',
    cleartext: true,
  },
  android: {
    buildOptions: {
      keystorePath: 'release.keystore',
      keystoreAlias: 'theapp',
    },
  },
}

export default config
