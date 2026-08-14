import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';

import {
  assertHeliosConfigured,
  HELIOS_API_BASE,
  HELIOS_API_HEADERS,
} from '@/constants/helios';

type AlertEvent = {
  id: number;
  kind: string;
  severity: 'success' | 'warning' | 'critical';
  title: string;
  message: string;
  created_at: string;
  read_at: string | null;
};

const alertsUrl = `${HELIOS_API_BASE.replace(/\/energy$/, '')}/alerts`;

export default function AlertsScreen() {
  const router = useRouter();
  const [items, setItems] = useState<AlertEvent[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [pushStatus, setPushStatus] = useState('');

  const loadAlerts = useCallback(async () => {
    try {
      assertHeliosConfigured();
      const response = await fetch(alertsUrl, { headers: HELIOS_API_HEADERS });
      if (!response.ok) throw new Error(`Alert request failed (${response.status})`);
      const data = await response.json();
      setItems(data.items);
      setUnreadCount(data.unread_count);
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load alerts');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  async function markRead(id: number) {
    const response = await fetch(`${alertsUrl}/${id}/read`, {
      method: 'PUT',
      headers: HELIOS_API_HEADERS,
    });
    if (response.ok) await loadAlerts();
  }

  async function markAllRead() {
    const response = await fetch(`${alertsUrl}/read-all`, {
      method: 'PUT',
      headers: HELIOS_API_HEADERS,
    });
    if (response.ok) await loadAlerts();
  }

  async function enablePush() {
    try {
      if (Platform.OS !== 'web' || !('serviceWorker' in navigator) || !('PushManager' in window)) {
        throw new Error('Install the Helios web app on a supported phone first.');
      }
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') throw new Error('Notification permission was not granted.');
      const configResponse = await fetch(`${alertsUrl}/push-config`, { headers: HELIOS_API_HEADERS });
      if (!configResponse.ok) throw new Error('Push configuration is unavailable.');
      const { public_key: publicKey } = await configResponse.json();
      if (!publicKey) throw new Error('Push notifications are not configured yet.');
      const registration = await navigator.serviceWorker.register('/service-worker.js');
      const existing = await registration.pushManager.getSubscription();
      const subscription = existing ?? await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });
      const response = await fetch(`${alertsUrl}/push-subscriptions`, {
        method: 'POST',
        headers: { ...HELIOS_API_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify(subscription),
      });
      if (!response.ok) throw new Error('Helios could not save this phone.');
      setPushStatus('Push notifications enabled on this device.');
    } catch (caught) {
      setPushStatus(caught instanceof Error ? caught.message : 'Unable to enable notifications.');
    }
  }

  async function sendTestNotification() {
    try {
      const response = await fetch(`${alertsUrl}/test-notification`, {
        method: 'POST', headers: HELIOS_API_HEADERS,
      });
      if (!response.ok) throw new Error('Unable to send the test notification.');
      const result = await response.json();
      if (result.sent > 0) {
        setPushStatus(`Test notification sent to ${result.sent} subscribed device${result.sent === 1 ? '' : 's'}.`);
      } else if (result.failed > 0) {
        setPushStatus('Your device is subscribed, but the push service rejected delivery.');
      } else if (result.removed > 0) {
        setPushStatus('The saved subscription expired. Enable notifications again.');
      } else {
        setPushStatus('No subscribed device yet. Enable notifications first.');
      }
    } catch (caught) {
      setPushStatus(caught instanceof Error ? caught.message : 'Test notification failed.');
    }
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => {
          setRefreshing(true);
          loadAlerts();
        }} tintColor="#FDB813" />
      }
    >
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={styles.back}>‹</Text>
        </Pressable>
        <View style={styles.heading}>
          <Text style={styles.title}>Alert center</Text>
          <Text style={styles.subtitle}>{unreadCount} unread</Text>
        </View>
        <Pressable onPress={markAllRead} disabled={unreadCount === 0}>
          <Text style={[styles.markAll, unreadCount === 0 && styles.disabled]}>Read all</Text>
        </Pressable>
      </View>

      {Platform.OS === 'web' ? (
        <View style={styles.pushCard}>
          <Text style={styles.pushTitle}>Lock-screen notifications</Text>
          <Text style={styles.pushText}>Enable after adding Helios to your iPhone Home Screen.</Text>
          <Pressable style={styles.pushButton} onPress={enablePush}>
            <Text style={styles.pushButtonText}>Enable notifications</Text>
          </Pressable>
          <Pressable style={styles.testButton} onPress={sendTestNotification}>
            <Text style={styles.testButtonText}>Send test notification</Text>
          </Pressable>
          {pushStatus ? <Text style={styles.pushStatus}>{pushStatus}</Text> : null}
        </View>
      ) : null}

      {loading ? <ActivityIndicator color="#FDB813" style={styles.loader} /> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {!loading && !error && items.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyTitle}>All quiet</Text>
          <Text style={styles.emptyText}>New energy events will appear here automatically.</Text>
        </View>
      ) : null}
      {items.map((item) => (
        <Pressable
          key={item.id}
          onPress={() => !item.read_at && markRead(item.id)}
          style={[styles.card, !item.read_at && styles.unread]}
        >
          <View style={[styles.dot, styles[`dot_${item.severity}`]]} />
          <View style={styles.cardBody}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>{item.title}</Text>
              {!item.read_at ? <Text style={styles.newLabel}>NEW</Text> : null}
            </View>
            <Text style={styles.message}>{item.message}</Text>
            <Text style={styles.time}>{new Date(item.created_at).toLocaleString()}</Text>
          </View>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#071018' },
  content: { paddingHorizontal: 20, paddingTop: 58, paddingBottom: 50 },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 24 },
  back: { color: '#FDB813', fontSize: 42, lineHeight: 42, marginRight: 12 },
  heading: { flex: 1 },
  title: { color: '#FFFFFF', fontSize: 28, fontWeight: '900' },
  subtitle: { color: '#74838E', fontSize: 13, marginTop: 2 },
  markAll: { color: '#FDB813', fontSize: 13, fontWeight: '800' },
  pushCard: { backgroundColor: '#14252E', borderRadius: 20, padding: 18, marginBottom: 18 },
  pushTitle: { color: '#FFFFFF', fontSize: 16, fontWeight: '800' },
  pushText: { color: '#84939D', fontSize: 12, lineHeight: 18, marginTop: 5 },
  pushButton: { backgroundColor: '#FDB813', borderRadius: 14, padding: 12, marginTop: 14, alignItems: 'center' },
  pushButtonText: { color: '#071018', fontSize: 13, fontWeight: '900' },
  testButton: { borderColor: '#FDB813', borderWidth: 1, borderRadius: 14, padding: 12, marginTop: 10, alignItems: 'center' },
  testButtonText: { color: '#FDB813', fontSize: 13, fontWeight: '900' },
  pushStatus: { color: '#A6B2B9', fontSize: 12, marginTop: 10 },
  disabled: { opacity: 0.35 },
  loader: { marginTop: 40 },
  error: { color: '#FF8A80', backgroundColor: '#28171A', padding: 16, borderRadius: 16 },
  empty: { backgroundColor: '#0D1820', borderRadius: 22, padding: 28, alignItems: 'center' },
  emptyTitle: { color: '#FFFFFF', fontSize: 18, fontWeight: '800' },
  emptyText: { color: '#84939D', fontSize: 13, textAlign: 'center', marginTop: 8 },
  card: { backgroundColor: '#0D1820', borderRadius: 18, padding: 16, marginBottom: 10, flexDirection: 'row' },
  unread: { backgroundColor: '#14252E', borderColor: '#24414F', borderWidth: 1 },
  dot: { width: 9, height: 9, borderRadius: 5, marginTop: 5, marginRight: 12 },
  dot_success: { backgroundColor: '#49D17D' },
  dot_warning: { backgroundColor: '#FDB813' },
  dot_critical: { backgroundColor: '#FF625F' },
  cardBody: { flex: 1 },
  cardHeader: { flexDirection: 'row', alignItems: 'center' },
  cardTitle: { color: '#FFFFFF', fontSize: 15, fontWeight: '800', flex: 1 },
  newLabel: { color: '#FDB813', fontSize: 10, fontWeight: '900', marginLeft: 8 },
  message: { color: '#A6B2B9', fontSize: 13, lineHeight: 19, marginTop: 6 },
  time: { color: '#65737C', fontSize: 11, marginTop: 10 },
});

function urlBase64ToUint8Array(value: string) {
  const padding = '='.repeat((4 - value.length % 4) % 4);
  const base64 = (value + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  return Uint8Array.from([...raw].map((character) => character.charCodeAt(0)));
}
