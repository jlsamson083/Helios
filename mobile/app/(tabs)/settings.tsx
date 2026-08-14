import {
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { passkeysSupported, registerPasskey } from '@/utils/passkeys';
import { HELIOS_API_BASE } from '@/constants/helios';

export default function SettingsScreen() {
  const router = useRouter();
  const [faceIdStatus, setFaceIdStatus] = useState('');

  async function setUpFaceId() {
    try {
      await registerPasskey();
      setFaceIdStatus('Face ID is ready for future sign-ins.');
    } catch (caught) {
      setFaceIdStatus(caught instanceof Error ? caught.message : 'Face ID setup failed.');
    }
  }

  async function signOut() {
    await fetch(`${HELIOS_API_BASE.replace(/\/energy$/, '')}/auth/logout`, { method: 'POST' });
    if (Platform.OS === 'web') window.location.reload();
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
    >
      <Text style={styles.title}>Settings</Text>
      <Text style={styles.subtitle}>
        Helios energy preferences
      </Text>

      <Pressable
        accessibilityRole="button"
        onPress={() => router.push('/(tabs)/alerts')}
        style={styles.alertLink}
      >
        <View>
          <Text style={styles.alertTitle}>Alert center</Text>
          <Text style={styles.alertText}>Grid, battery, export, and Solis events</Text>
        </View>
        <Text style={styles.alertArrow}>›</Text>
      </Pressable>

      {Platform.OS === 'web' && passkeysSupported() ? (
        <View style={styles.faceCard}>
          <Text style={styles.alertTitle}>Face ID unlock</Text>
          <Text style={styles.alertText}>Create an Apple passkey after signing in with your account.</Text>
          <Pressable style={styles.faceButton} onPress={setUpFaceId}>
            <Text style={styles.faceButtonText}>Set up Face ID</Text>
          </Pressable>
          {faceIdStatus ? <Text style={styles.faceStatus}>{faceIdStatus}</Text> : null}
        </View>
      ) : null}

      <SettingRow
        label="Critical battery reserve"
        value="30%"
      />

      <SettingRow
        label="Tesla-ready battery SOC"
        value="50%"
      />

      <SettingRow
        label="Minimum Tesla current"
        value="6 A"
      />

      <SettingRow
        label="Maximum Tesla current"
        value="32 A"
      />

      <View style={styles.note}>
        <Text style={styles.noteTitle}>
          Read-only for now
        </Text>

        <Text style={styles.noteText}>
          These values currently show the rules configured in
          the Helios backend. Editing them from the app will be
          added later.
        </Text>
      </View>

      {Platform.OS === 'web' ? (
        <Pressable style={styles.signOutButton} onPress={signOut}>
          <Text style={styles.signOutText}>Sign out / switch account</Text>
        </Pressable>
      ) : null}
    </ScrollView>
  );
}

function SettingRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <View style={styles.row}>
      <Text style={styles.label}>
        {label}
      </Text>

      <Text style={styles.value}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#071018',
  },

  content: {
    paddingHorizontal: 20,
    paddingTop: 64,
    paddingBottom: 50,
  },

  title: {
    color: '#FFFFFF',
    fontSize: 32,
    fontWeight: '900',
  },

  subtitle: {
    color: '#74838E',
    fontSize: 14,
    marginTop: 4,
    marginBottom: 28,
  },

  row: {
    backgroundColor: '#0D1820',
    borderRadius: 18,
    padding: 18,
    marginBottom: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },

  alertLink: {
    backgroundColor: '#14252E',
    borderColor: '#24414F',
    borderWidth: 1,
    borderRadius: 20,
    padding: 18,
    marginBottom: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },

  alertTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '800',
  },

  alertText: {
    color: '#84939D',
    fontSize: 12,
    marginTop: 4,
  },

  alertArrow: {
    color: '#FDB813',
    fontSize: 30,
    lineHeight: 32,
  },

  faceCard: { backgroundColor: '#14252E', borderRadius: 20, padding: 18, marginBottom: 18 },
  faceButton: { backgroundColor: '#FDB813', borderRadius: 14, padding: 12, alignItems: 'center', marginTop: 14 },
  faceButtonText: { color: '#071018', fontSize: 13, fontWeight: '900' },
  faceStatus: { color: '#A6B2B9', fontSize: 12, marginTop: 10 },

  label: {
    color: '#B2BEC5',
    fontSize: 14,
  },

  value: {
    color: '#FDB813',
    fontSize: 14,
    fontWeight: '800',
  },

  note: {
    backgroundColor: '#14252E',
    borderRadius: 22,
    padding: 20,
    marginTop: 10,
  },

  noteTitle: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '800',
  },

  noteText: {
    color: '#84939D',
    fontSize: 13,
    lineHeight: 20,
    marginTop: 8,
  },

  signOutButton: { borderColor: '#5B3134', borderWidth: 1, borderRadius: 16, padding: 14, alignItems: 'center', marginTop: 18 },
  signOutText: { color: '#FF8E92', fontSize: 13, fontWeight: '800' },
});
