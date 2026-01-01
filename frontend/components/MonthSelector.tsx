"use client"
import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"

export default function MonthSelector() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const currentDate = new Date()
  const currentMonth = String(currentDate.getMonth() + 1).padStart(2, '0')
  const currentYear = String(currentDate.getFullYear())

  const month = searchParams.get('month') || currentMonth
  const year = searchParams.get('year') || currentYear

  const goToPreviousMonth = () => {
    let newMonth = parseInt(month) - 1
    let newYear = parseInt(year)

    if (newMonth < 1) {
      newMonth = 12
      newYear -= 1
    }

    router.push(`?month=${String(newMonth).padStart(2, '0')}&year=${newYear}`)
  }

  const goToNextMonth = () => {
    let newMonth = parseInt(month) + 1
    let newYear = parseInt(year)

    if (newMonth > 12) {
      newMonth = 1
      newYear += 1
    }

    router.push(`?month=${String(newMonth).padStart(2, '0')}&year=${newYear}`)
  }

  const goToCurrentMonth = () => {
    router.push(`?month=${currentMonth}&year=${currentYear}`)
  }

  return (
    <div className="flex items-center justify-between">
      <Button variant="outline" size="icon" onClick={goToPreviousMonth}>
        <ChevronLeft className="h-4 w-4" />
      </Button>

      <div className="flex flex-col items-center">
        <h2 className="text-xl font-semibold">
          {new Date(parseInt(year), parseInt(month) - 1).toLocaleString("default", { month: "long", year: "numeric" })}
        </h2>
        <Button variant="link" size="sm" onClick={goToCurrentMonth}>
          Today
        </Button>
      </div>

      <Button variant="outline" size="icon" onClick={goToNextMonth}>
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  )
}

