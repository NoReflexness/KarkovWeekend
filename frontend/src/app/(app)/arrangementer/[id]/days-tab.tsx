"use client";

import { motion } from "framer-motion";

import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { formatDate } from "@/lib/format";
import type { KarkovEvent } from "@/lib/types";

import { AttendanceDialog } from "@/components/attendance-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function DaysTab({ event }: { event: KarkovEvent }) {
  const { user } = useAuth();
  const canToggle = event.status === "planlagt" || event.status === "aabent";

  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
      {event.days.map((day, idx) => {
        const isPresent = user ? day.attendee_user_ids.includes(user.id) : false;
        return (
          <motion.div
            key={day.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.04 }}
          >
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base capitalize">{formatDate(day.date)}</CardTitle>
                <p className="text-muted-foreground text-xs">
                  {day.attendee_user_ids.length} tilmeldte ·{" "}
                  {day.activities.length} aktiviteter
                </p>
              </CardHeader>
              <CardContent className="flex items-center justify-between gap-3">
                {isPresent ? (
                  <Badge>Tilmeldt</Badge>
                ) : (
                  <Badge variant="outline">Ikke tilmeldt</Badge>
                )}
                {canToggle && (
                  <AttendanceDialog
                    eventId={event.id}
                    day={day}
                    canToggle={canToggle}
                    trigger={
                      <Button size="sm" variant={isPresent ? "outline" : "default"}>
                        {da.events.attendance.manage}
                      </Button>
                    }
                  />
                )}
              </CardContent>
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}
