import {
    ScrollView,
    StyleSheet,
    Text,
    View,
} from 'react-native';

export default function SettingsScreen() {
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
    >
      <Text style={styles.title}>Settings</Text>
      <Text style={styles.subtitle}>
        Helios energy preferences
      </Text>

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
});