"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, Scale } from "lucide-react";

import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";

/**
 * OAuth / email-confirmation redirect target.
 *
 * The Supabase client is created with `detectSessionInUrl: true`, so on this
 * full page load it automatically parses the session from the URL — the hash
 * tokens of the implicit flow or the `?code=` of the PKCE flow — and fires
 * `onAuthStateChange`. We listen for that, with `getSession` polls as a backup,
 * and never exchange the code manually (which would double-spend it).
 */
export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let done = false;
    const finish = (path: string) => {
      if (done) return;
      done = true;
      router.replace(path);
    };

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) finish("/");
    });

    (async () => {
      const params = new URL(window.location.href).searchParams;
      const providerError =
        params.get("error_description") || params.get("error");
      if (providerError) {
        setError(providerError);
        return;
      }

      const { data } = await supabase.auth.getSession();
      if (data.session) {
        finish("/");
        return;
      }

      // Give detectSessionInUrl a moment to finish, then re-check.
      setTimeout(async () => {
        const { data: again } = await supabase.auth.getSession();
        if (again.session) {
          finish("/");
        } else {
          setError("Could not complete sign-in. Please try again.");
        }
      }, 2500);
    })();

    return () => subscription.unsubscribe();
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="flex flex-col items-center text-center">
        <span className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/15 text-primary">
          <Scale className="h-6 w-6" />
        </span>
        {error ? (
          <>
            <h1 className="font-serif text-xl font-medium tracking-tight">
              Sign-in failed
            </h1>
            <p className="mt-2 max-w-xs text-sm text-muted-foreground">{error}</p>
            <Button asChild className="mt-6">
              <Link href="/auth/login">Back to sign in</Link>
            </Button>
          </>
        ) : (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Completing sign-in…
          </p>
        )}
      </div>
    </main>
  );
}
