import { Tabs } from 'expo-router';
import React from 'react';

import { BurgerHeader } from '@/components/burger-header';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        header: () => <BurgerHeader />,
        tabBarStyle: { display: 'none' },
        sceneStyle: { backgroundColor: '#071018' },
      }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
        }}
      />
      <Tabs.Screen
        name="bill"
        options={{
          title: 'Bill',
        }}
      />
      <Tabs.Screen
        name="tesla"
        options={{
          title: 'Tesla',
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
        }}
      />
      <Tabs.Screen
        name="alerts"
        options={{ href: null }}
      />
      <Tabs.Screen
        name="finance"
        options={{ href: null, title: 'Finance' }}
      />
    </Tabs>
  );
}
