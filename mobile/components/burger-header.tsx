import { usePathname, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { HELIOS_API_BASE } from '@/constants/helios';

type Identity = { username: string; role: 'owner' | 'member' };

const MENU_ITEMS = [
  { label: 'Home', path: '/' },
  { label: 'History', path: '/history' },
  { label: 'Meralco Bill', path: '/bill' },
  { label: 'Tesla', path: '/tesla' },
  { label: 'Alerts', path: '/alerts' },
  { label: 'Settings', path: '/settings' },
] as const;

export function BurgerHeader() {
  const [open, setOpen] = useState(false);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    fetch(`${HELIOS_API_BASE.replace(/\/energy$/, '')}/auth/me`, {
      credentials: 'include',
      cache: 'no-store',
    })
      .then(async response => response.ok ? response.json() : null)
      .then(setIdentity)
      .catch(() => setIdentity(null));
  }, []);

  const items = identity?.role === 'owner'
    ? [...MENU_ITEMS.slice(0, 3), { label: 'Finance', path: '/finance' }, ...MENU_ITEMS.slice(3)]
    : MENU_ITEMS;

  function navigate(path: string) {
    setOpen(false);
    router.push(path as never);
  }

  return (
    <View style={styles.header}>
      <Pressable
        accessibilityLabel="Open navigation menu"
        onPress={() => setOpen(true)}
        style={styles.menuButton}>
        <Text style={styles.menuIcon}>☰</Text>
      </Pressable>
      <View style={styles.brand}>
        <Text style={styles.title}>HELIOS</Text>
        <Text style={styles.subtitle}>by Eros Enterprise</Text>
      </View>
      <View style={styles.menuButton} />

      <Modal
        animationType="fade"
        onRequestClose={() => setOpen(false)}
        transparent
        visible={open}>
        <View style={styles.overlay}>
          <View style={styles.drawer}>
            <View style={styles.drawerHeader}>
              <Text style={styles.drawerTitle}>Helios</Text>
              {identity && <Text style={styles.account}>{identity.username}</Text>}
            </View>
            {items.map(item => {
              const active = pathname === item.path || (item.path === '/' && pathname === '/index');
              return (
                <Pressable
                  key={item.path}
                  onPress={() => navigate(item.path)}
                  style={[styles.item, active && styles.activeItem]}>
                  <Text style={[styles.itemText, active && styles.activeText]}>{item.label}</Text>
                  {item.path === '/finance' && <Text style={styles.ownerBadge}>OWNER</Text>}
                </Pressable>
              );
            })}
          </View>
          <Pressable style={styles.dismissArea} onPress={() => setOpen(false)} />
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { height: 62, backgroundColor: '#0D1820', borderBottomColor: '#20303A', borderBottomWidth: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14 },
  menuButton: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  menuIcon: { color: '#FDB813', fontSize: 28, lineHeight: 32 },
  brand: { alignItems: 'center' },
  title: { color: '#F5F7F8', fontSize: 15, fontWeight: '900', letterSpacing: 1.5 },
  subtitle: { color: '#7F929D', fontSize: 10, marginTop: 1 },
  overlay: { flex: 1, flexDirection: 'row', backgroundColor: 'rgba(0,0,0,0.58)' },
  drawer: { width: 286, maxWidth: '82%', backgroundColor: '#0B151C', paddingTop: 58, paddingHorizontal: 16, gap: 6 },
  dismissArea: { flex: 1 },
  drawerHeader: { paddingHorizontal: 12, paddingBottom: 20, marginBottom: 6, borderBottomColor: '#20303A', borderBottomWidth: 1 },
  drawerTitle: { color: '#F5F7F8', fontSize: 28, fontWeight: '900' },
  account: { color: '#FDB813', fontSize: 12, marginTop: 5 },
  item: { minHeight: 48, borderRadius: 12, paddingHorizontal: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  activeItem: { backgroundColor: '#162932' },
  itemText: { color: '#B8C4CA', fontSize: 16, fontWeight: '600' },
  activeText: { color: '#FDB813' },
  ownerBadge: { color: '#8FDDBA', backgroundColor: '#123126', borderRadius: 7, overflow: 'hidden', paddingHorizontal: 7, paddingVertical: 4, fontSize: 9, fontWeight: '900' },
});
