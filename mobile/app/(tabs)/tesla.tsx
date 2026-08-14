import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
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
  const [targetSoc, setTargetSoc] = useState('80');
  const [departure, setDeparture] = useState(formatLocalDateTime(defaultDeparture()));

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
      const modeData: ChargingMode = await modeResponse.json();
      setMode((previous) => {
        if (!previous) {
          setTargetSoc(String(modeData.target_soc_percent ?? 80));
          if (modeData.departure_time) {
            setDeparture(formatLocalDateTime(new Date(modeData.departure_time)));
          }
        }
        return modeData;
      });
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
    if (!mode) return;
    try {
      setUpdating(true);
      setError(null);
      const target = Number(targetSoc);
      if (!Number.isFinite(target) || target < 0 || target > 100) {
        throw new Error('Target SOC must be between 0 and 100%.');
      }
      const departureDate = new Date(departure);
      if (nextMode === 'trip' && (
        Number.isNaN(departureDate.getTime()) || departureDate.getTime() <= Date.now()
      )) {
        throw new Error('Choose a future trip departure date and time.');
      }
      const response = await fetch(`${HELIOS_API_BASE}/charging-mode`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...HELIOS_API_HEADERS },
        body: JSON.stringify({
          mode: nextMode,
          simulated_tesla_soc_percent: mode.simulated_tesla_soc_percent,
          target_soc_percent: target,
          departure_time: nextMode === 'trip' ? departureDate.toISOString() : null,
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
          <ModeButton title="Trip" active={mode?.mode === 'trip'} disabled={updating} onPress={() => changeMode('trip')} />
          <ModeButton title="Charge now" active={mode?.mode === 'charge_now'} disabled={updating} onPress={() => changeMode('charge_now')} />
        </View>
        <View style={styles.tripFields}>
          <Text style={styles.fieldLabel}>TARGET SOC</Text>
          <View style={styles.socInputRow}>
            <TextInput
              keyboardType="number-pad"
              onChangeText={setTargetSoc}
              style={styles.input}
              value={targetSoc}
            />
            <Text style={styles.percent}>%</Text>
          </View>
          <Text style={styles.fieldLabel}>TRIP DEPARTURE</Text>
          <DateTimeInput value={departure} onChange={setDeparture} />
          <Text style={styles.tripHint}>Set the target and departure, then tap Trip.</Text>
        </View>
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

function DateTimeInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  if (Platform.OS !== 'web') {
    return (
      <TextInput
        autoCapitalize="none"
        onChangeText={onChange}
        placeholder="YYYY-MM-DDTHH:mm"
        placeholderTextColor="#657985"
        style={styles.dateInput}
        value={value}
      />
    );
  }
  return React.createElement('input', {
    type: 'datetime-local',
    value,
    onChange: (event: React.ChangeEvent<HTMLInputElement>) => onChange(event.target.value),
    style: {
      width: '100%', boxSizing: 'border-box', backgroundColor: '#18272F',
      border: '1px solid #2B414D', borderRadius: 12, color: '#FFFFFF',
      fontSize: 16, padding: 13, colorScheme: 'dark',
    },
  });
}

function defaultDeparture() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(7, 0, 0, 0);
  return date;
}

function formatLocalDateTime(date: Date) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
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
  tripFields: { gap: 8, marginTop: 6 },
  fieldLabel: { color: '#657985', fontSize: 10, fontWeight: '800', letterSpacing: 0.8, marginTop: 5 },
  socInputRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#18272F', borderRadius: 12, borderWidth: 1, borderColor: '#2B414D' },
  input: { flex: 1, color: '#FFFFFF', fontSize: 16, padding: 13 },
  dateInput: { backgroundColor: '#18272F', borderColor: '#2B414D', borderWidth: 1, borderRadius: 12, color: '#FFFFFF', fontSize: 16, padding: 13 },
  percent: { color: '#AAB5BB', fontSize: 16, fontWeight: '800', paddingRight: 14 },
  safety: { color: '#657985', textAlign: 'center', fontSize: 11, marginTop: 4 },
});
