import { DarkTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import 'react-native-reanimated';

import { HELIOS_API_BASE } from '@/constants/helios';
import { authenticateWithPasskey, passkeysSupported } from '@/utils/passkeys';

export const unstable_settings = {
  anchor: '(tabs)',
};

export default function RootLayout() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(
    Platform.OS === 'web' ? null : true,
  );
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (Platform.OS === 'web') {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => {
        controller.abort();
        setAuthenticated(false);
      }, 5000);
      fetch(`${HELIOS_API_BASE.replace(/\/energy$/, '')}/alerts`, {
        cache: 'no-store',
        credentials: 'include',
        signal: controller.signal,
      })
        .then((response) => setAuthenticated(response.ok))
        .catch(() => setAuthenticated(false))
        .finally(() => window.clearTimeout(timeout));
      return () => {
        window.clearTimeout(timeout);
        controller.abort();
      };
    }
  }, []);

  async function signIn() {
    const response = await fetch(`${HELIOS_API_BASE.replace(/\/energy$/, '')}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.trim(), password }),
    });
    if (!response.ok) {
      setError('That username or password is not valid.');
      return;
    }
    setAuthenticated(true);
  }

  async function faceIdSignIn() {
    try {
      await authenticateWithPasskey();
      setAuthenticated(true);
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Face ID failed.');
    }
  }

  if (Platform.OS === 'web' && authenticated === null) {
    return (
      <View style={styles.loading}>
        <Text style={styles.sun}>☀</Text>
      </View>
    );
  }

  if (Platform.OS === 'web' && authenticated === false) {
    return (
      <View style={styles.login}>
        <Text style={styles.sun}>☀</Text>
        <Text style={styles.loginTitle}>Helios</Text>
        <Text style={styles.loginText}>Sign in once. This device will remember your session.</Text>
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          onChangeText={setUsername}
          placeholder="Username"
          placeholderTextColor="#65737C"
          style={styles.input}
          value={username}
        />
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          onChangeText={setPassword}
          onSubmitEditing={signIn}
          placeholder="Password"
          placeholderTextColor="#65737C"
          secureTextEntry
          style={[styles.input, styles.passwordInput]}
          value={password}
        />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Pressable onPress={signIn} style={styles.button}>
          <Text style={styles.buttonText}>Sign in</Text>
        </Pressable>
        {passkeysSupported() ? (
          <Pressable onPress={faceIdSignIn} style={styles.faceButton}>
            <Text style={styles.faceButtonText}>Unlock with Face ID</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }

  return (
    <ThemeProvider value={DarkTheme}>
      <Stack>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
      </Stack>
      <StatusBar style="light" />
    </ThemeProvider>
  );
}

const styles = StyleSheet.create({
  loading: { flex: 1, backgroundColor: '#071018', alignItems: 'center', justifyContent: 'center' },
  login: { flex: 1, backgroundColor: '#071018', justifyContent: 'center', padding: 28 },
  sun: { color: '#FDB813', fontSize: 48, textAlign: 'center' },
  loginTitle: { color: '#FFFFFF', fontSize: 36, fontWeight: '900', textAlign: 'center', marginTop: 8 },
  loginText: { color: '#84939D', fontSize: 14, lineHeight: 20, textAlign: 'center', marginTop: 8, marginBottom: 26 },
  input: { color: '#FFFFFF', backgroundColor: '#0D1820', borderColor: '#24414F', borderWidth: 1, borderRadius: 16, padding: 16, fontSize: 16 },
  passwordInput: { marginTop: 12 },
  error: { color: '#FF8A80', fontSize: 12, marginTop: 10 },
  button: { backgroundColor: '#FDB813', borderRadius: 16, padding: 15, alignItems: 'center', marginTop: 14 },
  buttonText: { color: '#071018', fontSize: 15, fontWeight: '900' },
  faceButton: { borderColor: '#FDB813', borderWidth: 1, borderRadius: 16, padding: 15, alignItems: 'center', marginTop: 12 },
  faceButtonText: { color: '#FDB813', fontSize: 15, fontWeight: '900' },
});
