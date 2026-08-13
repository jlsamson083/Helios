import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import {
  assertHeliosConfigured,
  HELIOS_API_BASE,
  HELIOS_API_HEADERS,
} from '@/constants/helios';

type Mode = 'solar' | 'trip' | 'charge_now';
type ChargingMode = {
  mode: Mode;
  simulated_tesla_soc_percent: number;
  target_soc_percent: number | null;
  departure_time: string | null;
  simulation: boolean;
};
type Status = {
  tesla: {
    battery_level_percent: number;
    charging_state: string;
    charging_power_kw: number;
    connected: boolean;
  };
  tesla_controller: {
    action: string;
    reason: string;
    target_current_a: number;
  };
};

export default function TeslaScreen() {
  const [mode, setMode] = useState<ChargingMode | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      assertHeliosConfigured();
      const [modeResponse, statusResponse] = await Promise.all([
        fetch(`${HELIOS_API_BASE}/charging-mode`, { headers: HELIOS_API_HEADERS }),
        fetch(`${HELIOS_API_BASE}/status`, { headers: HELIOS_API_HEADERS }),
      ]);
      if (!modeResponse.ok || !statusResponse.ok) {
        throw new Error('Unable to load simulated Tesla status');
      }
      setMode(await modeResponse.json());
      setStatus(await statusResponse.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to reach Helios');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15_000);
    return () => clearInterval(interval);
  }, [load]);

  const changeMode = async (nextMode: Mode) => {
    if (!mode || nextMode === 'trip') return;
    try {
      setUpdating(true);
      const response = await fetch(`${HELIOS_API_BASE}/charging-mode`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...HELIOS_API_HEADERS },
        body: JSON.stringify({
          mode: nextMode,
          simulated_tesla_soc_percent: mode.simulated_tesla_soc_percent,
          target_soc_percent: mode.target_soc_percent ?? 80,
          departure_time: null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? 'Unable to change mode');
      setMode(data);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to change mode');
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return <View style={styles.center}><ActivityIndicator size="large" color="#E82127" /></View>;
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor="#E82127" />}>
      <View style={styles.brandRow}>
        <Image
          source={require('../../assets/images/tesla-logo.png')}
          style={styles.logo}
          resizeMode="contain"
        />
        <View style={styles.simulationBadge}>
          <Text style={styles.simulationText}>SIMULATION ONLY</Text>
        </View>
      </View>

      <Text style={styles.title}>Tesla charging</Text>
      <Text style={styles.subtitle}>Solar-aware charging controls</Text>

      {error && <Text style={styles.error}>{error}</Text>}

      <View style={styles.vehicleCard}>
        <Text style={styles.eyebrow}>SIMULATED VEHICLE</Text>
        <Text style={styles.soc}>{mode?.simulated_tesla_soc_percent.toFixed(0)}%</Text>
        <Text style={styles.status}>
          {status?.tesla.charging_state ?? 'Disconnected'} · {status?.tesla.charging_power_kw.toFixed(1) ?? '0.0'} kW
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Charging mode</Text>
        <View style={styles.modeRow}>
          <ModeButton title="Solar" active={mode?.mode === 'solar'} disabled={updating} onPress={() => changeMode('solar')} />
          <ModeButton title="Charge now" active={mode?.mode === 'charge_now'} disabled={updating} onPress={() => changeMode('charge_now')} />
        </View>
        <Text style={styles.tripHint}>
          Trip mode and departure scheduling remain available on Home.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.eyebrow}>HELIOS DECISION</Text>
        <Text style={styles.cardTitle}>{status?.tesla_controller.action ?? 'Waiting'}</Text>
        <Text style={styles.body}>{status?.tesla_controller.reason ?? 'Waiting for energy data.'}</Text>
        <Text style={styles.current}>
          Target current: {status?.tesla_controller.target_current_a ?? 0} A
        </Text>
      </View>

      <Text style={styles.safety}>
        No real Tesla commands are sent during Sprint 1.
      </Text>
    </ScrollView>
  );
}

function ModeButton({ title, active, disabled, onPress }: {
  title: string;
  active: boolean;
  disabled: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable disabled={disabled} onPress={onPress} style={[styles.modeButton, active && styles.modeButtonActive]}>
      <Text style={[styles.modeText, active && styles.modeTextActive]}>{title}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#071018' },
  content: { paddingHorizontal: 20, paddingTop: 58, paddingBottom: 50, gap: 14 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#071018' },
  brandRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  logo: { width: 82, height: 62, backgroundColor: '#F8F8F8', borderRadius: 10 },
  simulationBadge: { backgroundColor: '#35171A', paddingHorizontal: 10, paddingVertical: 7, borderRadius: 9 },
  simulationText: { color: '#FF8E92', fontSize: 10, fontWeight: '800', letterSpacing: 0.8 },
  title: { color: '#FFFFFF', fontSize: 32, fontWeight: '900' },
  subtitle: { color: '#74838E', fontSize: 14, marginTop: -10, marginBottom: 8 },
  error: { color: '#FF8D8D', backgroundColor: '#32191C', padding: 12, borderRadius: 12 },
  vehicleCard: { backgroundColor: '#14252E', borderRadius: 24, padding: 22 },
  card: { backgroundColor: '#0D1820', borderRadius: 20, padding: 19, gap: 10 },
  eyebrow: { color: '#E82127', fontSize: 11, fontWeight: '800', letterSpacing: 1.2 },
  soc: { color: '#FFFFFF', fontSize: 48, fontWeight: '900', marginTop: 6 },
  status: { color: '#98A7AF', fontSize: 14 },
  cardTitle: { color: '#FFFFFF', fontSize: 21, fontWeight: '800' },
  body: { color: '#84939D', fontSize: 14, lineHeight: 21 },
  current: { color: '#D7E0E4', fontSize: 13, fontWeight: '700' },
  modeRow: { flexDirection: 'row', gap: 10 },
  modeButton: { flex: 1, paddingVertical: 13, borderRadius: 12, alignItems: 'center', backgroundColor: '#18272F' },
  modeButtonActive: { backgroundColor: '#E82127' },
  modeText: { color: '#AAB5BB', fontWeight: '700' },
  modeTextActive: { color: '#FFFFFF' },
  tripHint: { color: '#657985', fontSize: 12 },
  safety: { color: '#657985', textAlign: 'center', fontSize: 11, marginTop: 4 },
});
