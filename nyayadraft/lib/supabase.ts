import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    "Missing Supabase configuration. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local."
  );
}

/**
 * Browser Supabase client (singleton).
 *
 * This is a client-only SPA, so we use `@supabase/supabase-js` directly with
 * localStorage-backed session persistence rather than the cookie-based
 * `@supabase/ssr` integration. The default client flow is the implicit flow:
 * after OAuth the session lands in the URL and `detectSessionInUrl` parses it,
 * which `app/auth/callback` relies on.
 */
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
