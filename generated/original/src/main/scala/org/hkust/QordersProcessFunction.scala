import scala.math.Ordered.orderingToOrdered
import org.hkust.BasedProcessFunctions.RelationFKCoProcessFunction
import org.hkust.RelationType.Payload
import java.util.Date
import scala.util.matching.Regex
class QordersProcessFunction extends RelationFKCoProcessFunction[Any]("orders",1,Array("CUSTKEY"),Array("ORDERKEY"),false, true) {
override def isValid(value: Payload): Boolean = {
   if( (value("O_ORDERDATE").asInstanceOf[java.util.Date]<format.parse("1995-03-13")) ){
   true}else{
   false}
}
}
